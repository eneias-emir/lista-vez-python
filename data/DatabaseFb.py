from firebird.driver import Error, connect, driver_config, DriverConfig
import configparser
import datetime
from pydantic import BaseModel

STM_GET_GENERATOR = """
select gen_id(%s, 1) as NEW_GEN from RDB$DATABASE
"""

STM_SELECT_LISTA_VEZ = """
select ID_LV, ORDEM_LV, COD_ATENDENTE_LV, ID_STATUS_LV, RE.NOME_RE, coalesce(LM.DESC_LM, '') as DESC_MOTIVO
    from LISTA_VEZ LV
    left join REPRESENTANTE RE on RE.COD_RE = LV.COD_ATENDENTE_LV
    left join LISTA_VEZ_MOTIVO LM on LM.ID_LM = LV.ID_MOTIVO_LV
    where DATA_LV = '%s'
    order by ID_STATUS_LV, ORDEM_LV
"""

STM_INSERT_LISTA_VEZ = """
insert into LISTA_VEZ(ID_LV, DATA_LV, ID_STATUS_LV, VENDA_EFETUADA_LV, ORDEM_LV, COD_ATENDENTE_LV)
  values(%i, CURRENT_DATE, 1, 'N', coalesce((select max(ORDEM_LV) from LISTA_VEZ where DATA_LV = CURRENT_DATE), 0) + 10, %i)
"""

STM_INSERT_LISTA_VEZ_LOG_STATUS = """
insert into LISTA_VEZ_LOG_STATUS(ID_LL, HORA_LL, ID_STATUS_LL, ID_LISTA_VEZ_LL)
  values(gen_id(ID_LISTA_VEZ_LOG_STATUS, 1), CURRENT_TIME, %i, %i)
"""

# sql para verificar se existem registros para o atendente com status 1(aguardando), 2(em atendimento) ou 3(ocupado)
STM_SELECT_ATENDENTE_EM_ATIVIDADE = """
select count(*) as QT_REG
    from LISTA_VEZ 
    where DATA_LV = '%s'
    and COD_ATENDENTE_LV = %i
    and ID_STATUS_LV < 4
"""

STM_UPDATE_STATUS_LISTA_VEZ = """
update LISTA_VEZ
  set ID_STATUS_LV = {id_novo_status},
      VENDA_EFETUADA_LV = '{venda_efetuada}',
      ID_MOTIVO_LV = {id_motivo},
      ID_PREVENDA_LV = {id_prevenda},
      OBS_LV = '{obs}'
where ID_LV = {id_lista_vez}
"""

STM_SELECT_ATENDENTE_ATIVO = """
select COD_RE, 
       NOME_RE 
  from REPRESENTANTE 
  where ATIVO_RE = '{ativo}' 
  and TIPO_RE = '{tipo}'
  order by NOME_RE
"""

# classe usada para receber os parametros POST do metodo de atualizar prevenda
class Prevenda(BaseModel):
    num_prevenda: int
    cod_atendente: int
    manter_em_atendimento: str | None = None


class DatabaseFb():
    TAG_DISPONIVEIS = "disponiveis"
    TAG_EM_ATENDIMENTO = "em_atendimento"
    TAG_OCUPADOS = "ocupados"

    ID_STATUS_ATIVO = 1
    ID_STATUS_EM_ATENDIMENTO = 2
    ID_STATUS_OCUPADO = 3
    ID_STATUS_FINALIZADO = 4

    con = None

    def connect(self):
        config = configparser.ConfigParser()
        config.read('config.cfg')

        fbclient_path = config['database']['fbclient_path']
        database_name = config['database']['database_name']

        print("fbclient_path", fbclient_path)
        print("database_name", database_name)

        # DriverConfig.fb_client_library = fbclient_path

        driver_config.fb_client_library.value = fbclient_path
        driver_config.read('database.cfg')

        # Attach to database
        self.con = connect(database_name)

    def disconnect(self):
        self.con.close()

    def get_lista_status(self) -> list:
        result = []

        cur = self.con.cursor()
        cur.execute('select ID_LM, DESC_LM, ID_STATUS_LM from LISTA_VEZ_MOTIVO where STATUS_LM = ? order by DESC_LM', 'A')
        for (ID_LM, DESC_LM, ID_STATUS_LM) in cur:
            result.append(dict(id = ID_LM, descricao = DESC_LM.title(), id_status = ID_STATUS_LM))

        cur.close()

        return result

    def get_new_generator(self, nome_generator: str) -> int:
        cur = self.con.cursor()
        cur.execute(STM_GET_GENERATOR % nome_generator)

        rows = cur.fetchall()

        result = rows[0][0]

        return result

    def get_atendente_ativo(self) -> list:
        result = []

        cur = self.con.cursor()
        cur.execute(STM_SELECT_ATENDENTE_ATIVO.format(ativo='S', tipo='001'))

        for (COD_RE, NOME_RE) in cur:
            result.append(dict(cod_atendente = COD_RE, nome_atendente = NOME_RE.title()))

        cur.close()

        return result


    def atendente_em_atividade(self, cod_atendente: int) -> bool:
        data_atual = datetime.datetime.now().date()

        cur = self.con.cursor()
        #cur.execute(STM_SELECT_LISTA_VEZ.format(data_atual, cod_atendente ) )
        cur.execute(STM_SELECT_ATENDENTE_EM_ATIVIDADE % (data_atual.strftime("%Y-%m-%d"), cod_atendente))

        rows = cur.fetchall()

        qtde_reg = rows[0][0]
        #print("qtde reg", qtde_reg)

        cur.close()

        if qtde_reg == 0:
            return False
        else:
            return True

    def get_lista_vez(self) -> dict:
        result = {self.TAG_DISPONIVEIS: [], self.TAG_EM_ATENDIMENTO: [], self.TAG_OCUPADOS: []}

        #stm = self.get_statement_lista_vez()
        data_atual = datetime.datetime.now().date()

        cur = self.con.cursor()
        cur.execute(STM_SELECT_LISTA_VEZ % (data_atual.strftime("%Y-%m-%d") ) )

        for (id_lista_vez, ordem, cod_atendente, id_status, nome_atendente, desc_motivo) in cur:
            if (id_status == self.ID_STATUS_ATIVO):
                key = self.TAG_DISPONIVEIS
            elif (id_status == self.ID_STATUS_EM_ATENDIMENTO):
                key = self.TAG_EM_ATENDIMENTO
            elif (id_status == self.ID_STATUS_OCUPADO):
                key = self.TAG_OCUPADOS
            else:
                key = "none"

            if key != "none":
                result[key].append(dict(id_lista_vez = id_lista_vez,
                                        cod_atendente = cod_atendente,
                                        nome_atendente = nome_atendente.title()[0:20],
                                        ordem = ordem,
                                        id_status = id_status,
                                        desc_motivo = desc_motivo.title() ) )

        cur.close()

        return result


    def add_lista_vez(self, cod_atendente: int) -> dict:
        id_lista_vez = self.get_new_generator('ID_LISTA_VEZ')
        id_status = self.ID_STATUS_ATIVO

        result = {'id_lista_vez': id_lista_vez, 'warning': '', 'error': ''}

        cur = self.con.cursor()
        try:
            # Execute the insert statement
            cur.execute(STM_INSERT_LISTA_VEZ % (id_lista_vez, cod_atendente) )
            cur.execute(STM_INSERT_LISTA_VEZ_LOG_STATUS % (id_status, id_lista_vez) )

            self.con.commit()
        except Error as e:
            # Rollback the transaction in case of an error
            self.con.rollback()

            print("Error:", e)
            mensagem = str(e)
            result['error'] = f"error {mensagem}"

        finally:
            # Close the cursor and connection
            cur.close()

        return result

    def get_status_lista_vez(self, id_lista_vez: int) -> tuple:
        cur = self.con.cursor()
        try:
            # Execute the insert statement
            cur.execute('select ID_STATUS_LV, COD_ATENDENTE_LV from LISTA_VEZ where ID_LV = %i' % (id_lista_vez) )
            rows = cur.fetchall()

            id_status_atual = rows[0][0]
            cod_atendente = rows[0][1]

        except Error as e:
            # Rollback the transaction in case of an error
            self.con.rollback()

            print("Error:", e)
            id_status_atual = 0
            cod_atendente   = 0
        finally:
            # Close the cursor and connection
            cur.close()

        return id_status_atual, cod_atendente
    def alt_status_lista_vez(self, id_lista_vez: int, id_novo_status: int, id_motivo: int, id_prevenda: int, obs: str, venda_efetuada: str) -> dict:
        result = {self.TAG_DISPONIVEIS: [], self.TAG_EM_ATENDIMENTO: [], self.TAG_OCUPADOS: [], 'warning': '', 'error': ''}

        id_status_atual, cod_atendente = self.get_status_lista_vez(id_lista_vez)

        cur = self.con.cursor()
        try:
            cur.execute(STM_UPDATE_STATUS_LISTA_VEZ.format(id_novo_status = id_novo_status, venda_efetuada = venda_efetuada, id_motivo = id_motivo, id_prevenda = id_prevenda, obs = obs, id_lista_vez = id_lista_vez) )

            cur.execute(STM_INSERT_LISTA_VEZ_LOG_STATUS % (id_novo_status, id_lista_vez) )

            self.con.commit()
        except Error as e:
            # Rollback the transaction in case of an error
            self.con.rollback()

            print("Error:", e)
            mensagem = str(e)
            result['error'] = f"Insert error: {mensagem}"
        finally:
            # Close the cursor and connection
            cur.close()

        # insere um novo registro na lista da vez, a menos que tenha finalizado o expediente (status de 1 para 4)
        if id_novo_status == self.ID_STATUS_FINALIZADO and ( (id_status_atual == self.ID_STATUS_EM_ATENDIMENTO) or (id_status_atual == self.ID_STATUS_OCUPADO) ):
            self.add_lista_vez(cod_atendente)

        return result

    def get_id_lista_vez_atendente(self, cod_atendente: int) -> tuple:
        id_lista_vez = -1
        id_status_atual = -1

        data_atual = datetime.datetime.now().date()

        cur = self.con.cursor()
        cur.execute("select first 1 ID_LV, ID_STATUS_LV from LISTA_VEZ where DATA_LV = '%s' and COD_ATENDENTE_LV = %i and ID_STATUS_LV in(1, 2, 3)" % (data_atual.strftime("%Y-%m-%d"), cod_atendente))

        reg = cur.fetchone()
        if reg is not None:
            id_lista_vez = reg[0]
            id_status_atual = reg[1]

        cur.close()

        return id_lista_vez, id_status_atual
    def lancar_prevenda(self, prevenda: Prevenda) -> dict:
        result = {"result": 0, "warnings": "", "error": ""}

        cod_atendente = prevenda.cod_atendente
        id_lista_vez, id_status_atual = self.get_id_lista_vez_atendente(cod_atendente)

        if id_lista_vez == -1:
            data_ret = self.add_lista_vez(cod_atendente)
            id_lista_vez = data_ret['id_lista_vez']
            id_status_atual = self.ID_STATUS_ATIVO

        # se o registro nao esta como em atendimento, muda para em atendimento antes de efetuar a venda
        if id_status_atual != self.ID_STATUS_EM_ATENDIMENTO:
            self.alt_status_lista_vez(id_lista_vez, self.ID_STATUS_EM_ATENDIMENTO, 0, 0, '', 'N')

        self.alt_status_lista_vez(id_lista_vez, self.ID_STATUS_FINALIZADO, 0, prevenda.num_prevenda, '', 'S')

        if prevenda.manter_em_atendimento is not None and prevenda.manter_em_atendimento == 'S':
            id_lista_vez, id_status_atual = self.get_id_lista_vez_atendente(cod_atendente)
            if id_lista_vez > 0:
                self.alt_status_lista_vez(id_lista_vez, self.ID_STATUS_EM_ATENDIMENTO, 0, 0, '', 'N')

        result["result"] = id_lista_vez

        return result