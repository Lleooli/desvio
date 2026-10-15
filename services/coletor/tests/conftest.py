import os

# Os testes não leem o .env de quem roda: resultado igual em qualquer máquina.
os.environ["PV_ENV_FILE"] = ""
