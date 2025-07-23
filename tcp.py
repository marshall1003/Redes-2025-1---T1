import socket
import threading

class Conexao:
    def __init__(self, sock, addr, servidor):
        self.sock = sock
        self.addr = addr
        self.servidor = servidor
        self.fechado = False

    def enviar(self, dados):
        try:
            self.sock.sendall(dados)
        except Exception:
            self.fechar()

    def fechar(self):
        if not self.fechado:
            self.fechado = True
            try:
                self.sock.close()
            except Exception:
                pass
            self.servidor.conexao_fechada(self)

class Servidor:
    def __init__(self, porta, dados_recebidos):
        self.porta = porta
        self.dados_recebidos = dados_recebidos
        self.conexoes = set()
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', porta))
        self.sock.listen()
        threading.Thread(target=self._aceitar, daemon=True).start()

    def _aceitar(self):
        while True:
            try:
                sock, addr = self.sock.accept()
                conexao = Conexao(sock, addr, self)
                self.conexoes.add(conexao)
                threading.Thread(target=self._receber, args=(conexao,), daemon=True).start()
            except Exception:
                break

    def _receber(self, conexao):
        while not conexao.fechado:
            try:
                dados = conexao.sock.recv(4096)
                if not dados:
                    break
                self.dados_recebidos(conexao, dados)
            except Exception:
                break
        conexao.fechar()

    def conexao_fechada(self, conexao):
        self.conexoes.discard(conexao)