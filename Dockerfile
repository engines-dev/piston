FROM python:slim
WORKDIR /app

# install python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Language server setups, as of right now, just doing redudant work as multilspy
# it's useful to be explicit in case we change things in the future

# python langauge server, same as multilspy==0.0.12's requirements
RUN pip install --no-cache-dir jedi-language-server==0.41.1

# typescript language server, same as multilspy==0.0.12's runtime dependencies found in
# src/multilspy/language_servers/typescript_language_server/runtime_dependencies.json
RUN apt update && \
    apt install -y nodejs npm && \
    npm install --omit=dev --global typescript@5.5.4 typescript-language-server@4.3.3 && \
    npm cache clean --force && \
    apt remove -y npm && \
    apt autoremove -y

# copy over code
COPY src /app/src
# start the server
CMD ["fastapi", "run", "--host", "0.0.0.0", "--port", "8000", "src/app.py"]
