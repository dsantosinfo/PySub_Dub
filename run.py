# run.py

import uvicorn
import os
from dotenv import load_dotenv

def main():
    """
    Ponto de entrada principal para iniciar o servidor da API.

    As tarefas de administração, como a criação de usuários, foram movidas
    para scripts dedicados (ex: create_user.py) para melhor organização.
    """
    load_dotenv()

    # Inicia o servidor Uvicorn.
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    # O reload é desativado por padrão para garantir estabilidade em ambientes
    # containerizados. Para desenvolvimento local, o comando recomendado é:
    # uvicorn app.main:app --reload
    reload_status = False
    
    uvicorn.run(
        "app.main:app", host=host, port=port, reload=reload_status, workers=1
    )

if __name__ == "__main__":
    main()