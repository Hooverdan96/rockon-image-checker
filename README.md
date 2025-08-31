# Functional Specification: Container Image Checker

## Purpose and Description

The `container_image_checker.py` program is a robust Python script designed to verify the availability of container images across various public registries. Its primary function is to check if a specified image exists and, where possible, report its last publication date. This is particularly useful for maintaining up-to-date lists of containerized applications, such as those found in a Rock-on repository. By automatically parsing image strings from JSON files, the program streamlines the process of validating dependencies. It intelligently identifies the correct registry (e.g., Docker Hub, GitHub Container Registry, or Codeberg) and makes the appropriate API calls to check an image's status. This automated checking process is crucial for preventing broken links, ensuring application dependencies are healthy, and providing a quick, at-a-glance overview of the state of the container ecosystem. It helps developers, system administrators, and project maintainers proactively identify and resolve issues related to image unavailability or outdated versions, which is a key component of a robust and secure software supply chain. For example, a missing or outdated image can introduce critical security vulnerabilities or cause a deployment pipeline to fail unexpectedly, highlighting the need for a tool that can provide continuous, automated verification.

## Core Functionality

The program's core logic revolves around a few key steps. First, it locates and reads JSON files from a specified directory, which defaults to `./configs` but can be configured at runtime. It then extracts container image and tag information from these files by traversing the JSON structure to find the `"image"` and `"tag"` fields. For each `image:tag` combination found, the program uses a dispatcher function to determine the appropriate registry based on the image string's URL prefix. This intelligent routing is the heart of the program's flexibility. The dispatcher then calls a dedicated function to query that specific registry's API. For instance, if the image string is `ghcr.io/myuser/myimage`, the program will automatically route the check to the function responsible for querying the GitHub Container Registry API. This modular design ensures that the program can be easily extended to support new container registries by simply adding a new checking function without modifying the core parsing and dispatch logic. After all checks are complete, the program compiles the results, including the image status and last published date, into a structured format for display.

## Prerequisites

### Python Dependencies

The program requires several Python packages that can be installed using `pip`.

* **For running the program:**

```

pip install requests

```

The **`requests`** library is a fundamental dependency for this program, as it handles all of the HTTP requests made to the various container registry APIs. It provides a simple, yet powerful API for sending web requests, handling responses, managing headers and authentication, and automatically parsing data formats like JSON.

* **For running the unit tests (in `test_checker.py`):**

```

pip install requests
pip install requests-mock

```

The **`requests-mock`** library is essential for simulating API calls during testing. By intercepting outgoing requests and providing predefined responses, it allows the unit tests to verify the program's logic without relying on a live network connection, making the tests faster, more reliable, and independent of external services. This is particularly useful for testing failure cases, such as a 404 Not Found response or a network timeout, which are difficult to reproduce consistently in a live environment.

## API Token Configuration

To query container registries that require authentication, such as GitHub's Container Registry, you must provide a Personal Access Token (PAT) or a JSON Web Token (JWT). Providing these tokens allows the program to access private or protected resources that are not available to unauthenticated users, ensuring it can perform a comprehensive check of all images, regardless of their public or private status.

### GitHub Personal Access Token (PAT)

A **GitHub Classic PAT** is required to check images on `ghcr.io`, particularly for private repositories. The token must have a minimum scope of `read:packages`, which grants read-only access to packages and container images associated with your account or organization. This specific permission is a core principle of "least privilege" as it provides just enough access for the API to provide information about the container images without granting broader access to your GitHub account or other sensitive data. It's a crucial security measure that helps protect your account in the event the token is compromised.

* **How to obtain a GitHub PAT:**

1. Go to your GitHub profile settings.

2. Navigate to **Developer settings** > **Personal access tokens** > **Tokens (classic)**.

3. Click **Generate new token (classic)**.

4. Give the token a descriptive name and set an expiration date.

5. Under **Select scopes**, check the box for `read:packages`.

6. Click **Generate token**.

7. Copy the generated token immediately. It will not be shown again.

* **Note:** Unlike some other GitHub API calls, the `ghcr.io` API used by this program does **not** require the PAT to be Base64 encoded. This simplifies the token's usage and integration into the program's authentication headers, making it more straightforward to use directly in the command line.

### Codeberg JSON Web Token (JWT)

Checking private images on Codeberg requires a JWT token. This token is a self-contained, digitally signed token that securely transmits information about an entity to the registry's API, acting as a secure credential. The JWT proves your identity to the registry's API and authorizes access to the requested resources based on the embedded claims and permissions.

* **How to obtain a Codeberg JWT token:**

1. Log in to your Codeberg account.

2. Go to your profile settings.

3. Navigate to **Applications** > **Manage access tokens**.

4. Click **Generate New Token**.

5. Provide a name for the token and select the appropriate scopes for the repository access you need.

6. Click **Generate Token** and copy the resulting JWT.

## Execution and Output

### Program Execution Options

The program's behavior can be controlled using the following command-line flags.

* `--image` or `-i`: Checks a single image instead of scanning the JSON directory. This option overrides the default behavior and is useful for quickly verifying a new image's availability before adding it to your configuration files.

* `--github-token` or `-g`: Provides a GitHub Personal Access Token for authenticating with `ghcr.io`. This is necessary for checking private images.

* `--codeberg-token` or `-c`: Provides a Codeberg JWT token for authenticating with `codeberg.org`. This is required for accessing private images on this registry.

* `--directory` or `-d`: Specifies the directory where the JSON configuration files are located. If not specified, the program defaults to `./configs`. This allows for flexibility in project structure.

* `--output-format` or `-o`: Selects the format for the final report. Supported formats include `console` (default), `json`, `html`, and `markdown`.

### Results Representation

The output format can be tailored to suit different needs, from a simple console view to a machine-readable JSON object or a formatted report.

* **Console:** The default output. The results are displayed in a human-readable table with columns for **Rockon**, **Image**, **Version**, **Status**, and **Last Published**. This is the best option for immediate, interactive use in a terminal.

* **Markdown:** Presents the same tabular data as the console output, but in a format suitable for Markdown files. This is great for including a status report in a README file or a project wiki.

* **JSON:** Outputs the results as a structured JSON array, where each object contains detailed information about a single image. This format is ideal for integration with other tools or automation scripts in a CI/CD pipeline, as it can be easily parsed by other programs.

* **HTML:** Generates a complete HTML file with a basic, styled table showing the results. This is useful for creating a shareable, self-contained report that can be viewed in any web browser without needing a specific viewer.

### Diagnostic Options

A single flag is available for diagnostic purposes to assist with debugging network and API issues.

* `--print-payload` or `-p`: This flag, when enabled, instructs the program to print the raw API request headers and response bodies for each check. This is an invaluable tool for troubleshooting why a specific image check might be failing or returning unexpected data. For example, a 403 Forbidden error response clearly indicates an authentication issue with the provided token, while an empty or malformed JSON payload from the API can point to an unexpected server response.
