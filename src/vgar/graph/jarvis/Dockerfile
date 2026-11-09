FROM python:3.11-slim@sha256:07d4824036af339fa1b6ef769cc99d9c10a141769538b52b3b597c84f7a7b535
ADD https://github.com/pythonJaRvis/pythonJaRvis.github.io/archive/8871b86494a1aec0095686ffa543994a7361af88.tar.gz /tmp/jarvis.tar.gz
RUN mkdir /opt/jarvis && tar -xzf /tmp/jarvis.tar.gz -C /opt/jarvis --wildcards --strip-components=4 '*/Jarvis/tool/Jarvis/*' && rm /tmp/jarvis.tar.gz
COPY boot.py /opt/jarvis/boot.py
WORKDIR /opt/jarvis
ENTRYPOINT ["python", "/opt/jarvis/boot.py"]
