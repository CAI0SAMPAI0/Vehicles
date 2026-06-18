import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv('GROQ_API_KEY')


def get_car_ai_bio(model, brand, year):
    prompt = '''
    Me mostre uma descrição de venda para o carro {} {} {} em apenas 250 caracteres. Informe coisas específicas do carro.
    '''.format(brand, model, year)
    client = Groq(api_key=GROQ_API_KEY)

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{'role': 'user', 'content': prompt}],
        max_tokens=500,
    )
    return response.choices[0].message.content


def get_car_ai_category(brand, model, year):
    """
    Consulta a Groq para classificar o veículo em uma das categorias fixas.
    Retorna uma string com o código da categoria (ex: 'SUV', 'SEDAN', 'CLASSICO').
    """
    categorias_validas = ['SEDAN', 'SUV', 'HATCH', 'PICAPE', 'ESPORTIVO', 'MINIVAN', 'ELETRICO', 'CLASSICO', 'OUTRO']

    prompt = f"""
Você é um especialista em automóveis. Classifique o carro "{brand} {model} {year or ''}" em UMA das seguintes categorias:
SEDAN, SUV, HATCH, PICAPE, ESPORTIVO, MINIVAN, ELETRICO, CLASSICO, OUTRO

Regras:
- Use CLASSICO para carros fabricados antes de 1990 ou modelos considerados ícones históricos.
- Use ELETRICO apenas para veículos 100% elétricos.
- Use ESPORTIVO para supercarros, carros esporte e modelos de alto desempenho.
- Use PICAPE para caminhonetes e pickups.
- Use SUV para utilitários esportivos e crossovers.
- Use HATCH para carros hatchback compactos.
- Use SEDAN para sedans e berlinas.
- Use MINIVAN para vans e minivans de passageiros.
- Use OUTRO apenas se nenhuma categoria se encaixar.

Retorne APENAS um JSON no formato:
{{"categoria": "CATEGORIA_AQUI"}}

Sem explicações adicionais.
"""

    try:
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=50,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content.strip()
        data = json.loads(content)
        categoria = data.get('categoria', 'OUTRO').upper().strip()
        if categoria not in categorias_validas:
            return 'OUTRO'
        return categoria
    except Exception as e:
        print(f"Aviso: Erro ao classificar categoria para {brand} {model}: {e}")
        return 'OUTRO'