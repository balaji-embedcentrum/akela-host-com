# Stand-in agent image for the provisioner test (emulates the hermes-adapter
# contract: /health on 8766, socket on 9000). NOT used in prod.
FROM python:3.12-slim
COPY server.py /server.py
EXPOSE 8766 9000
CMD ["python", "/server.py"]
