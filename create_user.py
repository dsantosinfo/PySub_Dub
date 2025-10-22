# create_user.py

import asyncio
import argparse
import logging
from dotenv import load_dotenv

# Configuração básica de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# É crucial carregar as variáveis de ambiente ANTES de importar os módulos da aplicação
load_dotenv()

from app import crud
from app.database import get_async_session_local
from app.schemas.user import UserCreate


async def main():
    """
    Ponto de entrada assíncrono para o script de criação de usuário.
    """
    parser = argparse.ArgumentParser(description="Cria um novo usuário e sua primeira chave de API.")
    parser.add_argument("email", type=str, help="O endereço de e-mail do novo usuário.")
    parser.add_argument("password", type=str, help="A senha para o novo usuário (mínimo 8 caracteres).")
    
    args = parser.parse_args()

    if len(args.password) < 8:
        logging.error("A senha deve ter no mínimo 8 caracteres.")
        return

    logging.info(f"Iniciando processo de criação para o usuário: {args.email}")

    session_factory = get_async_session_local()
    async with session_factory() as db:
        try:
            # 1. Verifica se o usuário já existe
            existing_user = await crud.get_user_by_email(db, email=args.email)
            if existing_user:
                logging.warning(f"Usuário com e-mail '{args.email}' já existe. Nenhuma ação foi tomada.")
                return

            # 2. Cria o novo usuário
            logging.info(f"Criando usuário {args.email} no banco de dados...")
            user_in = UserCreate(email=args.email, password=args.password)
            user = await crud.create_user(db, user_in)
            
            # 3. Gera a chave de API inicial
            logging.info(f"Gerando chave de API para {user.email}...")
            api_key_plaintext, _ = await crud.create_api_key_for_user(db, user=user)

            # 4. Exibe o resultado para o administrador
            print("\n" + "="*60)
            print("🎉 Usuário criado com sucesso!")
            print(f"   E-mail: {user.email}")
            print(f"   Sua chave de API é: {api_key_plaintext}")
            print("\nGuarde esta chave em um local seguro. Ela não poderá ser recuperada.")
            print("="*60 + "\n")

        except Exception as e:
            logging.error(f"Ocorreu um erro inesperado durante a criação do usuário: {e}", exc_info=True)


if __name__ == "__main__":
    # Exemplo de como usar no terminal:
    # python create_user.py admin@example.com SuaSenhaForte123
    asyncio.run(main())