# Rockon-image-checker
Determine age of underlying container images that are used in Rockstor's Rockons

## 1.0 Program Overview

This document provides a functional specification for the `container_checker.py`, a Python command-line utility designed to check the availability and last-published date of container images across various registries. This utility is specifically designed to check the images used in the Rock-on definitions found at the GitHub repository `rockstor/rockon-registry`. The program can operate in two primary modes: scanning a set of local JSON files for image references or checking a single, user-specified image. The program supports multiple output formats to present the results.

## 2.0 Functional Requirements

### 2.1 Execution Modes

The program operates in two distinct execution modes, which are determined by the presence of the -i or --image command-line flag.

1. **Scanning JSON Files (Default):**

   * When invoked without the `-i` or `--image` flag, the program will scan all `.json` files in its current directory.

   * It will extract all unique `<image>:<tag>` combinations found within these files.

   * The program will print a list of all identified image combinations to the console before initiating any network calls.

2. **Checking a Specific Image:**

   * When invoked with the `-i` or `--image` flag, the program will **only** check the image specified by the user. It will ignore all local JSON files.

   * If a tag is not provided (e.g., `-i nginx`), the `latest` tag will be assumed by default.

   * The program will print the specific image being processed to the console before checking its availability.

### 2.2 Command-Line Arguments

The script accepts several command-line arguments that control its operational mode, authentication, and output format.

* `-i`, `--image`: Specifies a single image to check. The format is `<image>:<tag>`.

* `-g`, `--github-token`: Provides a GitHub Personal Access Token for authenticating with `ghcr.io`. This can also be provided via the `GITHUB_TOKEN` environment variable.

* `-c`, `--codeberg-token`: Provides a JWT token for authenticating with `codeberg.org`. This can also be provided via the `CODEBERG_TOKEN` environment variable.

* `-p`, `--print-payload`: A flag that, when present, will print the full JSON payload received from each API response. This is for debugging purposes.

* `-o`, `--output-format`: Specifies the desired output format. The following options are supported:

  * `console` (Default): A well-formatted, human-readable table printed directly to the terminal.

  * `json`: A structured JSON array of all results.

  * `html`: A complete, responsive HTML document featuring a styled table.

  * `markdown`: A Markdown-formatted table.

### 2.3 Supported Registries and Authentication

The program is capable of checking images from the following registries. Authentication for these registries is handled in a tiered fashion: the program first checks for the command-line flag, and if not present, falls back to the corresponding environment variable.

* **Docker Hub:** Authenticates automatically via a temporary token fetch.

* **GitHub Container Registry (`ghcr.io`):** Requires a GitHub Personal Access Token passed via the `-g` or `--github-token` flag, or the **`GITHUB_TOKEN` environment variable**.

* **Codeberg Container Registry (`codeberg.org`):** Requires a JWT token passed via the `-c` or `--codeberg-token` flag, or the **`CODEBERG_TOKEN` environment variable**.

## 3.0 Result Presentation

Regardless of the execution mode, the final output will be a report detailing the availability and last published date for each image checked. The presentation of this report is determined by the `--output-format` flag.
