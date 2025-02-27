# base starts with both python and nodejs runtimes
# it's also the most convenient to install ruby-github-linguist here, even though it should
# technicaly be done at the final image only, we avoid redundant apt update by just doing it here
FROM python:slim AS base
RUN apt update \
  && apt install -y nodejs ruby-github-linguist \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# builder image
FROM base AS builder
WORKDIR /builder

# gcc is needed for some python packages
# git is needed for pip install
# npm is needed for typescript language server
RUN apt update && apt install -y gcc git npm

COPY requirements.txt /requirements.txt
RUN pip install --prefix=/builder -r /requirements.txt

# Language server setups, as of right now, just installing the same things that multilspy expects at
# runtime, this way we don't need to worry about it needing to install things on start up
# it's useful to be explicit in case we change things in the future

# python langauge server, same as multilspy==0.0.12's requirements
RUN pip install --prefix=/builder jedi-language-server==0.41.1

# typescript language server, same as multilspy==0.0.12's runtime dependencies found in
# src/multilspy/language_servers/typescript_language_server/runtime_dependencies.json
RUN npm install --omit=dev --global --prefix=/builder typescript@5.5.4 typescript-language-server@4.3.3
# RUN npm install --omit=dev --global typescript@5.5.4 typescript-language-server@4.3.3


# final image
FROM base
WORKDIR /app

# this copies over both python packages and node packages
COPY --from=builder /builder /usr/local

# copy over our code
COPY src /app/src

# start the server
CMD ["fastapi", "run", "--host", "0.0.0.0", "--port", "8000", "src/app.py"]

