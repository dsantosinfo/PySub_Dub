# app/core/encryption.py

import base64
from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings

class Encryptor:
    """
    Uma classe utilitária para lidar com criptografia e descriptografia simétrica.

    Usa o algoritmo Fernet da biblioteca 'cryptography'. A chave de
    criptografia é lida a partir das configurações da aplicação.
    """
    def __init__(self, key: str):
        if not key:
            raise ValueError("A ENCRYPTION_KEY não pode ser vazia.")
        
        try:
            # A chave Fernet deve ser 32 bytes codificados em URL-safe base64.
            # Decodificamos a chave da string para bytes.
            key_bytes = key.encode('utf-8')
            # Validamos se a chave é válida para o Fernet.
            base64.urlsafe_b64decode(key_bytes)
        except (ValueError, TypeError):
            raise ValueError("A ENCRYPTION_KEY fornecida não é uma chave base64 válida.")

        self.fernet = Fernet(key_bytes)

    def encrypt(self, data: str) -> str:
        """
        Criptografa uma string e retorna o resultado como uma string codificada.
        """
        if not isinstance(data, str):
            raise TypeError("O dado a ser criptografado deve ser uma string.")
            
        encrypted_bytes = self.fernet.encrypt(data.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')

    def decrypt(self, encrypted_data: str) -> str | None:
        """
        Descriptografa uma string previamente criptografada.

        Retorna None se a descriptografia falhar (ex: token inválido,
        chave incorreta), em vez de lançar uma exceção, para um
        manuseio mais seguro no código que a chama.
        """
        if not isinstance(encrypted_data, str):
            return None
            
        try:
            decrypted_bytes = self.fernet.decrypt(encrypted_data.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except InvalidToken:
            # Ocorre se a chave estiver incorreta, ou o dado estiver corrompido/alterado.
            return None
        except Exception:
            # Captura outras exceções inesperadas durante a descriptografia.
            return None

# Instância singleton para ser usada em toda a aplicação.
# Isso garante que a chave seja validada apenas uma vez na inicialização.
encryptor = Encryptor(key=settings.ENCRYPTION_KEY)