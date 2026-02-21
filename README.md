# MRX Documentation Site

This repository powers [mrx-org.github.io](https://mrx-org.github.io) — the documentation, examples, and public roadmaps for **MRX**, a project to create an AI assistant for MRI research and measurements.

## How It Works

The site is built with [Quartz v4](https://quartz.jzhao.xyz/), which converts Markdown files into a static website. This repository is a fork of [jackyzha0/quartz](https://github.com/jackyzha0/quartz); only the `content/` folder and minor customization files have been changed.

## Writing Content

All documentation lives in the `content/` folder as Markdown files. Quartz is fully compatible with [Obsidian](https://obsidian.md/), which is the recommended tool for authoring and organizing pages. Open the `content/` folder as an Obsidian vault to get started.

## Local Development

Prerequisites: [Node.js](https://nodejs.org/) (see `.node-version` for the expected version).

```sh
npm install
npx quartz build --serve
```

This starts a local preview server so you can see your changes before publishing.

## Publishing

Push your changes using Quartz's built-in sync command or any standard Git workflow:

```sh
npx quartz sync
```

A GitHub Actions workflow automatically builds and deploys the site on every push.

## Learn More

- [Quartz documentation](https://quartz.jzhao.xyz/)
- [Obsidian](https://obsidian.md/)
