import numpy as np
import matplotlib.pyplot as plt
import nibabel as nib
from pathlib import Path


# Reference intensity peaks (from your histogram estimates)
WM_I = 213.0
GM_I = 172.0
CSF_I = 1.0

# Approximate 3T tissue parameters (literature-based, typical values)
# Times are in seconds, ADC in mm^2/s, PD is relative proton density.
WM_T1, GM_T1, CSF_T1 = 0.9, 1.3, 3.7
WM_T2, GM_T2, CSF_T2 = 0.070, 0.080, 0.300
WM_T2S, GM_T2S, CSF_T2S = 0.050, 0.055, 0.080  # T2*
WM_ADC, GM_ADC, CSF_ADC = 0.7e-3, 0.9e-3, 3.0e-3
WM_PD, GM_PD, CSF_PD = 0.70, 0.86, 1.00


def _fit_quadratic(intensities: np.ndarray, values: np.ndarray):
    """
    Fit p(I) = a*I^2 + b*I + c through 3 points.
    """
    a, b, c = np.polyfit(intensities, values, 2)
    return a, b, c


def _apply_quad(intensity: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
    I = np.asarray(intensity, dtype=float)
    I_clamped = np.clip(I, CSF_I, WM_I)
    return a * I_clamped**2 + b * I_clamped + c


def plot_brain_histogram(
    nifti_path: str = "data/mni152_fixed.nii",
    bins: int = 100,
) -> None:
    """
    Load a NIfTI file and plot a histogram over all brain voxels.

    Brain voxels are approximated as all non-zero voxels.
    """
    img = nib.load(nifti_path)
    data = img.get_fdata()

    # Use non-zero voxels as a simple brain mask
    brain_voxels = data[data != 0]

    plt.figure()
    plt.hist(brain_voxels.ravel(), bins=bins)
    plt.xlabel("Intensity")
    plt.ylabel("Voxel count")
    plt.title(f"Histogram of brain voxels ({Path(nifti_path).name})")
    plt.tight_layout()
    plt.show()


def smooth_intensity_to_t1(intensity: np.ndarray) -> np.ndarray:
    """
    Map intensity → T1 (s) using a single quadratic fitted to
    (CSF_I, CSF_T1), (GM_I, GM_T1), (WM_I, WM_T1).
    """
    x = np.array([CSF_I, GM_I, WM_I], dtype=float)
    y = np.array([CSF_T1, GM_T1, WM_T1], dtype=float)
    a, b, c = _fit_quadratic(x, y)
    print(f"T1:  f(I) = {a:.6e} * I^2 + {b:.6e} * I + {c:.6e}")
    return _apply_quad(intensity, a, b, c)


def smooth_intensity_to_t2(intensity: np.ndarray) -> np.ndarray:
    """
    Map intensity → T2 (s) using a quadratic through WM/GM/CSF 3T values.
    """
    x = np.array([CSF_I, GM_I, WM_I], dtype=float)
    y = np.array([CSF_T2, GM_T2, WM_T2], dtype=float)
    a, b, c = _fit_quadratic(x, y)
    print(f"T2:  f(I) = {a:.6e} * I^2 + {b:.6e} * I + {c:.6e}")
    return _apply_quad(intensity, a, b, c)


def smooth_intensity_to_t2star(intensity: np.ndarray) -> np.ndarray:
    """
    Map intensity → T2* (s) using a quadratic through WM/GM/CSF 3T values.
    """
    x = np.array([CSF_I, GM_I, WM_I], dtype=float)
    y = np.array([CSF_T2S, GM_T2S, WM_T2S], dtype=float)
    a, b, c = _fit_quadratic(x, y)
    print(f"T2*: f(I) = {a:.6e} * I^2 + {b:.6e} * I + {c:.6e}")
    return _apply_quad(intensity, a, b, c)


def smooth_intensity_to_adc(intensity: np.ndarray) -> np.ndarray:
    """
    Map intensity → isotropic ADC (mm^2/s) using a quadratic.
    """
    x = np.array([CSF_I, GM_I, WM_I], dtype=float)
    y = np.array([CSF_ADC, GM_ADC, WM_ADC], dtype=float)
    a, b, c = _fit_quadratic(x, y)
    print(f"ADC: f(I) = {a:.6e} * I^2 + {b:.6e} * I + {c:.6e}")
    return _apply_quad(intensity, a, b, c)


def smooth_intensity_to_pd(intensity: np.ndarray) -> np.ndarray:
    """
    Map intensity → relative proton density (0–1) using a quadratic.
    """
    x = np.array([CSF_I, GM_I, WM_I], dtype=float)
    y = np.array([CSF_PD, GM_PD, WM_PD], dtype=float)
    a, b, c = _fit_quadratic(x, y)
    print(f"PD:  f(I) = {a:.6e} * I^2 + {b:.6e} * I + {c:.6e}")
    return _apply_quad(intensity, a, b, c)


def demo_intensity_to_property(
    nifti_path: str = "data/mni152_fixed.nii",
) -> None:
    """
    Load the NIfTI, convert intensities to T1, and plot a histogram
    of T1 values over all brain (non-zero) voxels.
    """
    img = nib.load(nifti_path)
    data = img.get_fdata()

    brain_voxels = data[data != 0]
    t1_vals = smooth_intensity_to_t1(brain_voxels)
    t2_vals = smooth_intensity_to_t2(brain_voxels)
    t2star_vals = smooth_intensity_to_t2star(brain_voxels)
    adc_vals = smooth_intensity_to_adc(brain_voxels)
    pd_vals = smooth_intensity_to_pd(brain_voxels)

    for vals, property in zip([t1_vals, t2_vals, t2star_vals, adc_vals, pd_vals], ["T1", "T2", "T2*", "ADC", "PD"]):
        plt.figure()
        plt.hist(vals.ravel(), bins=100)
        plt.xlabel(f"{property} (s)")
        plt.ylabel("Voxel count")
        plt.title(f"Histogram of brain {property} values")
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    plot_brain_histogram()
    demo_intensity_to_property()


