# Imagen base oficial de Apify para Python
FROM apify/actor-python:3.13

COPY requirements.txt ./
RUN echo "Python version:" && python --version \
    && echo "Installing dependencies:" && pip install -r requirements.txt \
    && echo "All installed."

COPY . ./
RUN python3 -m compileall -q src/

CMD ["python3", "-m", "src"]