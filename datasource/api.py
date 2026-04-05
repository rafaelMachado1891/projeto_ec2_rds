from requests import Session
from requests.exceptions import ConnectionError, TooManyRedirects, Timeout
from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from datetime import datetime
import psycopg2
import json
import os
import schedule
import time

load_dotenv()

url = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/quotes/latest'

parameters = {
    'symbol': 'BTC',
    'convert': 'USD'
}

headers = {
    'Accept': 'application/json',
    'X-CMC_PRO_API_KEY': os.getenv('API_KEY'),
}

session = Session()
session.headers.update(headers)

DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")


class Quote_model(BaseModel):
    price: float
    volume_24h: float = Field(alias='volume_24h')
    market_cap: float = Field(alias='market_cap')
    last_updated: datetime


class Bitcoin_model(BaseModel):
    symbol: str
    quote: dict

    def get_usd_quote(self) -> Quote_model:
        return Quote_model(**self.quote['USD'])


class ApiResponseBaseModel(BaseModel):
    data: dict
    status: dict

    def get_bitcoin_data(self) -> Bitcoin_model:
        return Bitcoin_model(**self.data['BTC'])


def criar_tabela():
    connection = None
    cursor = None

    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )

        cursor = connection.cursor()

        create_table_query = '''
        CREATE TABLE IF NOT EXISTS bitcoin_quotes (
            id SERIAL PRIMARY KEY,
            price FLOAT NOT NULL,
            volume_24h FLOAT NOT NULL,
            market_cap FLOAT NOT NULL,
            last_updated TIMESTAMP NOT NULL
        );
        '''

        cursor.execute(create_table_query)
        connection.commit()

        print("Tabela 'bitcoin_quotes' criada com sucesso.")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Erro ao criar tabela: {error}")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def salvar_cotacao_no_banco(quote: Quote_model):
    connection = None
    cursor = None

    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )

        cursor = connection.cursor()

        insert_query = '''
        INSERT INTO bitcoin_quotes (price, volume_24h, market_cap, last_updated)
        VALUES (%s, %s, %s, %s);
        '''

        cursor.execute(insert_query, (
            quote.price,
            quote.volume_24h,
            quote.market_cap,
            quote.last_updated
        ))

        connection.commit()

        print("Cotação do Bitcoin salva no banco de dados.")

    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Erro ao salvar cotação no banco: {error}")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


def consulta_cotacao_bitcoin():
    try:
        response = session.get(url, params=parameters, timeout=10)
        response.raise_for_status()

        data = response.json()

        api_response = ApiResponseBaseModel(**data)
        bitcoin_data = api_response.get_bitcoin_data()
        quote = bitcoin_data.get_usd_quote()

        print(f"Última cotação do Bitcoin: ${quote.price:.2f} USD")
        print(f"Volume 24h: ${quote.volume_24h:.2f} USD")
        print(f"Market Cap: ${quote.market_cap:.2f} USD")
        print(f"Última atualização: {quote.last_updated}")

        salvar_cotacao_no_banco(quote)

    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(f"Erro na requisição: {e}")

    except ValidationError as e:
        print(f"Erro ao validar a resposta da API: {e}")

criar_tabela()

schedule.every(1800).seconds.do(consulta_cotacao_bitcoin)

# Loop principal para manter o agendamento ativo
if __name__ == "__main__":
    print("Iniciando o agendamento para consultar a API a cada 30 minutos...")
    while True:
        schedule.run_pending()
        time.sleep(1)