# Piston (alpha)

Piston is a REST API service for running language servers in a Docker container.

This is alpha software. Much work remains to be done.

## Introduction

Piston is a language-agnostic API service that provides code intelligence capabilities through
language servers. It can automatically detect the programming language of a codebase and provide
features like:

- Finding symbol definitions
- Finding references to symbols
- Extracting document symbols
- Parsing and analyzing diff patches

Piston uses [tree-sitter](https://tree-sitter.github.io/tree-sitter/index.html) for code parsing and
analysis, and [multilspy](https://github.com/microsoft/multilspy) for language server protocol
integration.

## Docker Deployment

Piston is meant to be run with [Docker](https://www.docker.com/) because its main benefit is easy
packing of the needed language server binaries. You can either pull the pre-built Docker image from
Docker Hub or build it locally:

- Pull from GitHub Container Registry

```
docker pull ghcr.io/engines-dev/piston:latest
docker tag ghcr.io/engines-dev/piston:latest piston
```

- Build Docker image locally (after you have checked out the repository)

```
docker build --tag piston .
```

Once the Docker image is ready, run the image with the following command:

```
docker run --tty --rm --publish 8000:8000 --volume /path/to/workspace:/workspace piston
```

where `/path/to/workspace` is the path to your codebase. Without this volume mount, Piston will use
an example Python project in the container. The `curl` command examples below uses the example
project.

### Docker Image Environment Variables (optional)

- `WORKSPACE_ROOT`: Path to the workspace directory (default: `/workspace`)
- `CODE_LANGUAGE`: Explicitly set the code language (if not set, will be auto-detected)

## Endpoints

Piston provides several REST API endpoints:

### `GET /definitions`

Find definitions for a symbol at a specific location

```shell
curl "localhost:8000/definitions?path=main.py&line=8&column=11"
```

```json
{
  "definitions": [
    {
      "uri": "file:///workspace/main.py",
      "range": {
        "start": {
          "line": 5,
          "character": 4
        },
        "end": {
          "line": 5,
          "character": 12
        }
      },
      "absolutePath": "/workspace/main.py",
      "relativePath": "main.py"
    }
  ]
}
```

### `GET /references`

Find references to a symbol at a specific location

```shell
curl "localhost:8000/references?path=utils.py&line=0&column=4"
```

```json
{
  "references": [
    {
      "uri": "file:///workspace/main.py",
      "range": {
        "start": {
          "line": 0,
          "character": 18
        },
        "end": {
          "line": 0,
          "character": 25
        }
      },
      "absolutePath": "/workspace/main.py",
      "relativePath": "main.py"
    },
    {
      "uri": "file:///workspace/main.py",
      "range": {
        "start": {
          "line": 6,
          "character": 7
        },
        "end": {
          "line": 6,
          "character": 14
        }
      },
      "absolutePath": "/workspace/main.py",
      "relativePath": "main.py"
    },
    {
      "uri": "file:///workspace/utils.py",
      "range": {
        "start": {
          "line": 0,
          "character": 4
        },
        "end": {
          "line": 0,
          "character": 11
        }
      },
      "absolutePath": "/workspace/utils.py",
      "relativePath": "utils.py"
    }
  ]
}
```

### `GET /symbols`

Get all symbols in a file

```shell
curl "localhost:8000/symbols?path=utils.py"
```

```json
{
  "symbols": [
    {
      "name": "is_even",
      "kind": "Function",
      "range": {
        "start": {
          "line": 0,
          "character": 0
        },
        "end": {
          "line": 2,
          "character": 26
        }
      },
      "selectionRange": {
        "start": {
          "line": 0,
          "character": 4
        },
        "end": {
          "line": 0,
          "character": 11
        }
      },
      "detail": "def is_even"
    },
    {
      "name": "is_positive",
      "kind": "Function",
      "range": {
        "start": {
          "line": 4,
          "character": 0
        },
        "end": {
          "line": 6,
          "character": 21
        }
      },
      "selectionRange": {
        "start": {
          "line": 4,
          "character": 4
        },
        "end": {
          "line": 4,
          "character": 15
        }
      },
      "detail": "def is_positive"
    }
  ]
}
```

### `POST /patch-digest`

Analyze a diff patch and return a digest of the changes as well as the identifiers in the changed lines.

Given a diff patch such as this one:

```diff
diff --git main.py main.py
index 3f9a1e8..dc99c56 100644
--- main.py
+++ main.py
@@ -1,4 +1,4 @@
-from utils import is_even
+from utils import is_even, is_positive
 from data import Person


@@ -7,6 +7,8 @@ def greet_person(person):
     greeting = f"Hello, {person.name}!"
     if is_even(person.age):
         greeting += " You have an even age."
+    if is_positive(person.age):
+        greeting += " And you have a positive age. How surprising!"
     return greeting
```

```shell
curl \
  -X POST \
  -H "Content-Type: multipart/form-data" \
  -F "patch=@example-workspace/patch.diff" \
  "localhost:8000/patch-digest"
```

```json
{
  "digest": [
    {
      "old_file": "main.py",
      "new_file": "main.py",
      "changes": [
        {
          "line_index": 0,
          "text": "from utils import is_even",
          "type": "deletion",
          "identifiers": [
            {
              "name": "utils",
              "char_index": 5
            },
            {
              "name": "is_even",
              "char_index": 18
            }
          ]
        },
        {
          "line_index": 0,
          "text": "from utils import is_even, is_positive",
          "type": "addition",
          "identifiers": [
            {
              "name": "utils",
              "char_index": 5
            },
            {
              "name": "is_even",
              "char_index": 18
            },
            {
              "name": "is_positive",
              "char_index": 27
            }
          ]
        }
      ]
    },
    {
      "old_file": "main.py",
      "new_file": "main.py",
      "changes": [
        {
          "line_index": 9,
          "text": "    if is_positive(person.age):",
          "type": "addition",
          "identifiers": [
            {
              "name": "is_positive",
              "char_index": 7
            },
            {
              "name": "person",
              "char_index": 19
            },
            {
              "name": "age",
              "char_index": 26
            }
          ]
        },
        {
          "line_index": 10,
          "text": "        greeting += \" And you have a positive age. How surprising!\"",
          "type": "addition",
          "identifiers": [
            {
              "name": "greeting",
              "char_index": 8
            }
          ]
        }
      ]
    }
  ]
}
```

## Supported Languages

Currently, Piston supports:

- Python

Other languages can be added easily but Python is the only one tested so far.

## Local Development Setup

### Prerequisites

- Docker
- Python 3.13+

### Development Steps

1. Clone the repository:

   ```
   git clone https://github.com/engines-dev/piston.git
   cd piston
   ```

2. Install dependencies:

   ```
   uv venv
   source .venv/bin/activate
   uv pip install -r requirements-dev.txt
   ```

3. Run tests:

   ```
   pytest
   ```

4. Run the development server:

   ```
   docker run \
     --interactive --tty --rm \
     --publish 8000:8000 \
     --volume .:/app \
     --volume /path/to/workspace:/workspace \
     --entrypoint /bin/bash \
     piston -c "fastapi dev --host 0.0.0.0 src/app.py"
   ```
