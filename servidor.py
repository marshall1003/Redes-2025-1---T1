#!/usr/bin/env python3
import asyncio
from tcp import Servidor
import re

apelidos = {}  # Mapeia apelido.lower() -> conexao
canais = {}    # Mapeia canal.lower() -> set de conexões

def validar_nome(nome):
    return re.match(br'^[a-zA-Z][a-zA-Z0-9_-]*$', nome) is not None


def sair(conexao):
    if hasattr(conexao, 'apelido'):
        apelido = conexao.apelido
        apelido_lower = apelido.lower()
        # Notifica todos que compartilham canal
        canais_comum = set()
        for canal, membros in canais.items():
            if conexao in membros:
                canais_comum.add(canal)
        notificados = set()
        for canal in canais_comum:
            for membro in canais[canal]:
                if membro != conexao and membro not in notificados:
                    resposta = f":{apelido} QUIT :Connection closed\r\n".encode('utf-8')
                    membro.enviar(resposta)
                    notificados.add(membro)
        # Remove dos canais
        for canal in canais_comum:
            canais[canal].remove(conexao)
            if not canais[canal]:
                del canais[canal]
        # Remove do dicionário de apelidos
        if apelido_lower in apelidos and apelidos[apelido_lower] == conexao:
            del apelidos[apelido_lower]
    conexao.fechar()

def join(conexao, linha):
    canal = linha[5:].strip()
    if not (canal.startswith('#') and validar_nome(canal[1:].encode('utf-8'))):
        resposta = f":server 403 {canal} :No such channel\r\n".encode('utf-8')
        conexao.enviar(resposta)
    
    canal_lower = canal.lower()
    if canal_lower not in canais:
        canais[canal_lower] = set()
    canais[canal_lower].add(conexao)
    # Notifica todos do canal
    for membro in canais[canal_lower]:
        resposta = f":{conexao.apelido} JOIN :{canal}\r\n".encode('utf-8')
        print(resposta)
        membro.enviar(resposta)
    # Envia lista de membros (353 e 366)
    membros = sorted([m.apelido for m in canais[canal_lower] if hasattr(m, 'apelido')])
    apelido = conexao.apelido
    prefixo = f":server 353 {apelido} = {canal} :"
    max_len = 512 - len(prefixo) - 2  # 2 para \r\n
    linha_atual = ""
    for membro in membros:
        if linha_atual:
            if len(linha_atual) + 1 + len(membro) > max_len:
                resposta = f"{prefixo}{linha_atual}\r\n".encode('utf-8')
                conexao.enviar(resposta)
                linha_atual = membro
            else:
                linha_atual += " " + membro
        else:
            linha_atual = membro
    if linha_atual:
        resposta = f"{prefixo}{linha_atual}\r\n".encode('utf-8')
        conexao.enviar(resposta)
    resposta = f":server 366 {apelido} {canal} :End of /NAMES list.\r\n".encode('utf-8')
    conexao.enviar(resposta)

def nick(conexao, linha):
    apelido = linha[5:].strip()
    apelido_lower = apelido.lower()
    if not validar_nome(apelido.encode('utf-8')):
        resposta = f":server 432 * {apelido} :Erroneous nickname\r\n".encode('utf-8')
        conexao.enviar(resposta)
        print(resposta)
    elif hasattr(conexao, 'apelido') and apelido_lower in apelidos:
        resposta = f":server 433 {conexao.apelido} {apelido} :Nickname is already in use\r\n".encode('utf-8')
        print(resposta)
        conexao.enviar(resposta)
    elif apelido_lower in apelidos and apelidos[apelido_lower] != conexao:
        resposta = f":server 433 * {apelido} :Nickname is already in use\r\n".encode('utf-8')
        conexao.enviar(resposta)
        print(resposta)
    elif hasattr(conexao, 'apelido') and apelido_lower not in apelidos:
        antigo = conexao.apelido.lower()
        if antigo in apelidos:
            del apelidos[antigo]
        conexao.apelido = apelido
        apelidos[apelido_lower] = conexao
        resposta = f":{antigo} NICK {apelido}\r\n".encode('utf-8')
        print(resposta)
        conexao.enviar(resposta)
    else:
        # Remove apelido antigo, se houver
        if hasattr(conexao, 'apelido'):
            antigo = conexao.apelido.lower()
            if antigo in apelidos:
                del apelidos[antigo]
        conexao.apelido = apelido
        apelidos[apelido_lower] = conexao
        
        resposta1 = f":server 001 {apelido} :Welcome\r\n".encode('utf-8')
        resposta2 = f":server 422 {apelido} :MOTD File is missing\r\n".encode('utf-8')
        print(resposta1, resposta2)
        conexao.enviar(resposta1)
        conexao.enviar(resposta2)
    
def part(conexao, linha):
    args = linha[5:].strip().split()
    if not args:
        pass
    canal = args[0]
    canal_lower = canal.lower()
    if canal_lower in canais and conexao in canais[canal_lower]:
        # Notifica todos do canal
        for membro in list(canais[canal_lower]):
            resposta = f":{conexao.apelido} PART {canal}\r\n".encode('utf-8')
            print(resposta)
            membro.enviar(resposta)
        canais[canal_lower].remove(conexao)
        # Remove o canal se ficar vazio (opcional)
        if not canais[canal_lower]:
            del canais[canal_lower]

def privmsg(conexao, linha):
    if not hasattr(conexao, 'apelido'):
        pass
    try:
        resto = linha[8:]
        destinatario, mensagem = resto.split(' :', 1)
        destinatario = destinatario.strip()
    except ValueError:
        pass
    destinatario_lower = destinatario.lower()
    if destinatario_lower.startswith('#'):
        # Mensagem para canal
        if destinatario_lower in canais:
            for membro in canais[destinatario_lower]:
                if membro != conexao:
                    resposta = f":{conexao.apelido} PRIVMSG {destinatario} :{mensagem}\r\n".encode('utf-8')
                    membro.enviar(resposta)
    elif destinatario_lower in apelidos:
        # Mensagem privada
        destino = apelidos[destinatario_lower]
        remetente = conexao.apelido
        resposta = f":{remetente} PRIVMSG {destinatario} :{mensagem}\r\n".encode('utf-8')
        destino.enviar(resposta)

def dados_recebidos(conexao, dados):
    if dados == b'':
        print(conexao, 'conexão fechada')
        sair(conexao)
        return
    if not hasattr(conexao, 'buffer'):
        conexao.buffer = b''
    conexao.buffer += dados

    try:
        texto = conexao.buffer.decode('utf-8')
    except Exception:
        return

    linhas = texto.split('\r\n')
    conexao.buffer = linhas[-1].encode('utf-8')
    for linha in linhas[:-1]:
        if not linha:
            continue
        print(conexao, linha.encode('utf-8'))
        # Trata comando PING
        if linha.startswith('PING '):
            payload = linha[5:]
            resposta = f":server PONG server :{payload}\r\n".encode('utf-8')
            conexao.enviar(resposta)
        # Trata comando NICK
        elif linha.startswith('NICK '):
            nick(conexao, linha)
        # Trata comando JOIN
        elif linha.startswith('JOIN '):
            join(conexao, linha)
        # Trata comando PART
        elif linha.startswith('PART '):
            part(conexao, linha)
        # Trata comando PRIVMSG
        elif linha.startswith('PRIVMSG '):
            privmsg(conexao, linha)


def conexao_aceita(conexao):
    print(conexao, 'nova conexão')
    conexao.registrar_recebedor(dados_recebidos)


if __name__ == '__main__':
    servidor = Servidor(6667, dados_recebidos)
    import time
    while True:
        time.sleep(1)
