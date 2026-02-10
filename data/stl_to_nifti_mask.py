import numpy as np
import nibabel as nib
import os
import sys

def parse_stl_ascii(filepath):
    """
    Simple ASCII STL parser.
    Reads 'vertex x y z' lines and returns them as a numpy array.
    """
    verts = []
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip().lower()
                if line.startswith('vertex'):
                    parts = line.split()
                    if len(parts) >= 4:
                        verts.append([float(parts[1]), float(parts[2]), float(parts[3])])
    except Exception as e:
        print(f"Error reading STL file: {e}")
        return np.array([])
    return np.array(verts)

def stl_to_nifti_mask(stl_path, mask_dims=(128, 128, 1), output_path=None):
    """
    Converts an oriented box STL to a rotated NIfTI mask.
    The resulting NIfTI will have a rotated affine matrix that aligns with the box.
    """
    print(f"--- STL to FOV Mask Converter ---")
    print(f"Loading STL: {stl_path}")
    
    verts = parse_stl_ascii(stl_path)
    if len(verts) == 0:
        print("Error: No vertices found in STL. Ensure it is in ASCII format.")
        return
    
    # Get unique vertices (STL repeats them for each triangle)
    # Using a small tolerance for floating point comparisons
    unique_verts = np.unique(verts.round(decimals=5), axis=0)
    print(f"Found {len(unique_verts)} unique vertices (from {len(verts)} total).")
    
    if len(unique_verts) < 8:
        print("Warning: Found fewer than 8 unique vertices. The STL might not be a full box.")
    
    # 1. Use PCA (Principal Component Analysis) to find the box axes and center
    # This automatically finds the orientation and dimensions of any box.
    center = np.mean(unique_verts, axis=0)
    centered_verts = unique_verts - center
    
    # Covariance matrix of the vertices
    cov = np.cov(centered_verts.T)
    
    # Eigenvectors of the covariance matrix are the principal axes of the box
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    
    # Sort eigenvalues/eigenvectors so that the axes match the dimensions [X, Y, Z]
    # We sort by eigenvalue descending as a heuristic, but then we project to find actual lengths
    idx = eigenvalues.argsort()[::-1]
    axes = eigenvectors[:, idx] # 3x3 matrix where columns are the axes
    
    # Ensure a right-handed coordinate system (det = 1)
    if np.linalg.det(axes) < 0:
        axes[:, 2] = -axes[:, 2]
    
    # 2. Determine local dimensions by projecting vertices onto the axes
    projected = centered_verts @ axes
    min_proj = projected.min(axis=0)
    max_proj = projected.max(axis=0)
    local_size = max_proj - min_proj
    
    print(f"Calculated Center (World RAS): {center}")
    print(f"Calculated Local size (mm): {local_size}")
    print(f"Axes (Rotation Matrix):\n{axes}")
    
    # 3. Calculate voxel spacing for the requested matrix size
    # spacing = local_size / dims
    dims = np.array(mask_dims)
    spacing = local_size / dims
    print(f"Target Matrix Size: {mask_dims}")
    print(f"Voxel Spacing (mm): {spacing}")
    
    # 4. Construct the NIfTI Affine Matrix
    # The NIfTI affine maps voxel index (i, j, k) to world coordinate (x, y, z):
    # P_world = R * (local_0 + diag(spacing) * [i, j, k]^T) + Center
    # P_world = (R * diag(spacing)) * [i, j, k]^T + (R * local_0 + Center)
    
    # local_0 is the local coordinate of voxel (0, 0, 0) center in the PCA space
    # (Since we used centered_verts, the local space is centered at [0,0,0])
    local_0 = min_proj + spacing / 2
    
    # Translation part of the affine (world coordinate of voxel 0,0,0)
    translation = axes @ local_0 + center
    
    affine = np.eye(4)
    # The 3x3 part is the rotation matrix multiplied by the voxel spacing for each column
    affine[:3, :3] = axes * spacing
    affine[:3, 3] = translation
    
    print(f"Final Rotated Affine:\n{affine}")
    
    # 5. Create the mask data
    # Since the NIfTI grid is now perfectly aligned with the box,
    # the entire grid is "inside" the mask.
    mask_data = np.ones(mask_dims, dtype=np.uint8)
    
    # Create NIfTI image
    img = nib.Nifti1Image(mask_data, affine)
    
    # Ensure both qform and sform are set correctly for maximum compatibility (MITK, etc.)
    img.header.set_qform(affine, code=2) # SCANNER_ANAT
    img.header.set_sform(affine, code=2) # SCANNER_ANAT
    
    if output_path is None:
        output_path = os.path.splitext(stl_path)[0] + "_mask.nii"
        if not output_path.endswith('.nii'):
            output_path += '.nii'
    
    # Save
    nib.save(img, output_path)
    print(f"Successfully saved rotated NIfTI mask to: {output_path}")
    return output_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("\nUsage: python stl_to_nifti_mask.py <path_to_stl> [dimX dimY dimZ]")
        print("Example: python stl_to_nifti_mask.py fov-box-ras.stl 128 128 1\n")
        sys.exit(1)
    
    stl_file = sys.argv[1]
    
    # Default matrix size
    matrix_dims = (128, 128, 1)
    
    if len(sys.argv) >= 5:
        try:
            matrix_dims = (int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]))
        except ValueError:
            print("Error: Dimensions must be integers.")
            sys.exit(1)
            
    if not os.path.exists(stl_file):
        print(f"Error: File {stl_file} not found.")
        sys.exit(1)
        
    stl_to_nifti_mask(stl_file, matrix_dims)
