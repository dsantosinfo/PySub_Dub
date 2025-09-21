# run.py

import uvicorn
import os
import sys
import asyncio
from dotenv import load_dotenv

def main():
    """Ponto de entrada principal."""
    load_dotenv()
    
    # Lógica para executar comandos CLI
    if len(sys.argv) > 1:
        # Importações necessárias apenas para a CLI
        from app.database import AsyncSessionLocal
        from app.schemas.user import UserCreate
        from app import crud
        
        async def cli_runner():
            command = sys.argv[1]
            # Usamos um context manager para garantir que a sessão seja fechada
            async with AsyncSessionLocal() as db:
                if command == "create-user" and len(sys.argv) == 4:
                    email, password = sys.argv[2], sys.argv[3]
                    
                    # --- MELHORIA APLICADA AQUI ---
                    # 1. Verifica se o usuário já existe
                    existing_user = await crud.get_user_by_email(db, email=email)
                    if existing_user:
                        print(f"Usuário com e-mail '{email}' já existe. Nenhuma ação foi tomada.")
                        # Idealmente, aqui poderíamos oferecer a opção de resetar a senha ou gerar uma nova API key.
                        # Por enquanto, apenas informamos.
                        return

                    print(f"Criando usuário {email}...")
                    user_in = UserCreate(email=email, password=password)
                    user = await crud.create_user(db, user_in)

                    # 2. Cria a chave de API para o novo usuário
                    api_key_plaintext, _ = await crud.create_api_key_for_user(db, user=user)
                    
                    # 3. Lógica de criar a chave da Groq foi REMOVIDA daqui.
                    
                    print("\n" + "="*50)
                    print("Usuário criado com sucesso!")
                    print(f"E-mail: {email}")
                    print(f"Sua chave de API é: {api_key_plaintext}")
                    print("Guarde esta chave em um local seguro. Ela não poderá ser recuperada.")
                    print("="*50 + "\n")
                    print("Próximo passo: Use esta chave para se autenticar na API e definir sua chave da Groq.")


                elif command == "set-setting" and len(sys.argv) == 4:
                    key, value = sys.argv[2], sys.argv[3]
                    print(f"Definindo configuração: {key}...")
                    await crud.create_or_update_setting(db, key, value)
                    print("Configuração salva com sucesso!")

                else:
                    print("Comando CLI inválido.")
                    print("Uso:")
                    print("  python run.py create-user <email> <password>")
                    print("  python run.py set-setting <KEY> <VALUE>")
        
        asyncio.run(cli_runner())
        return

    # Inicia o servidor Uvicorn se nenhum comando CLI for passado
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    reload_status = os.getenv("ENV", "development") == "development"
    
    uvicorn.run(
        "app.main:app", host=host, port=port, reload=reload_status, workers=1
    )

if __name__ == "__main__":
    main()