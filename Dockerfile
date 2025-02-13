FROM python:slim

# multilspy
RUN pip install --no-cache-dir multilspy==0.0.12

# python LSP, same as multilspy==0.0.12's requirements
RUN pip install --no-cache-dir jedi-language-server==0.41.1

# typescript LSP, same as multilspy==0.0.12's runtime dependencies found in
# src/multilspy/language_servers/typescript_language_server/runtime_dependencies.json
RUN apt update && \
    apt install -y nodejs npm && \
    npm install --omit=dev --global typescript@5.5.4 typescript-language-server@4.3.3 && \
    npm cache clean --force && \
    apt remove -y npm && \
    apt autoremove -y
