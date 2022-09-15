FROM prefecthq/prefect:2-python3.10
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt
ADD /. /opt/prefect/flows