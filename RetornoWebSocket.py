class RetornoWebSocket:
    warning_message = ''
    error_message = ''
    lista_atendentes_ativos = []
    lista_vez = []

    def set_warning_message(self, message: str) -> None:
        self.warning_message = message

    def set_error_message(self, message: str) -> None:
        self.error_message = message

    def set_atendentes_ativos(self, lista: list) -> None:
        self.lista_atendentes_ativos = lista

    def set_lista_vez(self, lista: dict) -> None:
        print("set_lista_vez", lista)
        self.lista_vez = lista

    def clear(self) -> None:
        self.warning_message = ''
        self.error_message = ''
        self.lista_atendentes_ativos.clear()
        self.lista_vez.clear()

    def get_resp_padrao(self) -> dict:
        ret = {"warningMessage": self.warning_message,
               "errorMessage": self.error_message,
               "listaAtendentesAtivos": self.lista_atendentes_ativos,
               "listaVez": self.lista_vez
               }

        return ret
