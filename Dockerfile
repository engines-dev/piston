# base starts with both python and nodejs runtimes
FROM python:3.13-slim AS base
RUN apt update \
  && apt install -y nodejs \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# builder image
FROM base AS builder
WORKDIR /builder

# gcc is needed for some python packages
# git is needed for pip install
# npm is needed for typescript language server
# go is needed for enry
RUN apt update && apt install -y gcc git npm golang

COPY requirements.txt requirements.txt
RUN pip install --prefix=/builder -r requirements.txt

# install enry, which is used to detect the main language of a code base
# it's a port of github's linguist, but linguist stupidly only works on git repos, not just any
# directory, enry doesn't have that problem (and it's only a single executable instead of needing
# ruby and all the dependencies)
RUN GOBIN=/builder/bin go install github.com/go-enry/enry@latest


# Language server setups, as of right now, just installing the same things that multilspy expects at
# runtime, this way we don't need to worry about it needing to install things on start up
# it's useful to be explicit in case we change things in the future

# python langauge server, same as multilspy==0.0.12's requirements
RUN pip install --prefix=/builder jedi-language-server==0.41.1

# typescript language server, same as multilspy==0.0.12's runtime dependencies found in
# src/multilspy/language_servers/typescript_language_server/runtime_dependencies.json
RUN npm install --omit=dev --global --prefix=/builder typescript@5.5.4 typescript-language-server@4.3.3


# final image
FROM base
WORKDIR /app
ARG WORKSPACE_ROOT=/workspace
ARG CODE_LANGUAGE

ENV WORKSPACE_ROOT=${WORKSPACE_ROOT}
ENV CODE_LANGUAGE=${CODE_LANGUAGE}

# this copies over both python packages, node packages, and enry that we installed in the builder
COPY --from=builder /builder /usr/local

# copy over our code
COPY src /app/src

# copy over the example workspace
COPY example-workspace ${WORKSPACE_ROOT}

# start the server
EXPOSE 8000
CMD ["fastapi", "run", "--host", "0.0.0.0", "--port", "8000", "src/app.py"]

