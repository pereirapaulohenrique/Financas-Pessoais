from app import db
from app.models.base import BaseModel
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from decimal import Decimal
from enum import Enum

class TipoRepeticao(Enum):
    """Enum para os tipos de repetição permitidos."""
    UNICO = 'unico'
    DIARIO = 'diario'
    SEMANAL = 'semanal'
    MENSAL = 'mensal'
    
    @classmethod
    def choices(cls):
        return [(tipo.value, tipo.name.title()) for tipo in cls]

class Orcamento(BaseModel):
    """Modelo para orçamentos com lançamentos flexíveis."""
    __tablename__ = 'orcamento'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=False)
    valor_total = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    tipo = db.Column(db.String(20), nullable=False)  # Receita ou Despesa
    data_inicio = db.Column(db.Date, nullable=False)
    data_fim = db.Column(db.Date, nullable=False)
    
    # Tipos permitidos
    TIPOS = ['Receita', 'Despesa']

    # Relacionamentos
    categoria = db.relationship('Categoria', back_populates='orcamentos')
    lancamentos = db.relationship('OrcamentoLancamento', back_populates='orcamento', 
                                cascade='all, delete-orphan')
    historicos = db.relationship('OrcamentoHistorico', back_populates='orcamento')
    previsoes = db.relationship('OrcamentoPrevisao', back_populates='orcamento', 
                              cascade='all, delete-orphan')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.valor_total = Decimal('0.0')
        if 'lancamentos' in kwargs:
            self.valor_total = sum(Decimal(str(l.valor)) for l in kwargs['lancamentos'])

    def recalcular_valor_total(self):
        """Recalcula o valor total do orçamento baseado nos lançamentos."""
        self.valor_total = sum(Decimal(str(l.valor)) for l in self.lancamentos if not l.deleted_at)
        return self.valor_total

    def gerar_previsoes(self):
        """Gera previsões baseadas nos lançamentos cadastrados."""
        # Remove previsões não realizadas existentes
        OrcamentoPrevisao.query.filter_by(
            orcamento_id=self.id,
            realizado=False
        ).delete()
        
        for lancamento in self.lancamentos:
            if lancamento.deleted_at:
                continue
                
            # Gera as datas baseadas no padrão de repetição
            datas = lancamento.gerar_datas_lancamento(self.data_inicio, self.data_fim)
            
            # Cria uma previsão para cada data
            for data in datas:
                previsao = OrcamentoPrevisao(
                    orcamento_id=self.id,
                    data_prevista=data,
                    valor=lancamento.valor,
                    descricao=lancamento.descricao,
                    categoria_id=self.categoria_id  # Adicionando categoria_id
                )
                db.session.add(previsao)
                
        db.session.flush()

    def ajustar_previsoes_apos_transacao(self, transacao):
        """Ajusta as previsões após uma transação real ser registrada."""
        if transacao.tipo != self.tipo:
            return
                
        data_transacao = transacao.data
        valor_transacao = Decimal(str(transacao.valor))
        
        # Busca a previsão da data da transação
        previsao = OrcamentoPrevisao.query.filter(
            OrcamentoPrevisao.orcamento_id == self.id,
            OrcamentoPrevisao.data_prevista == data_transacao,
            OrcamentoPrevisao.realizado == False
        ).first()
        
        if previsao:
            # Mantém o valor original da previsão
            valor_original = Decimal(str(previsao.valor))
            
            # Marca como realizado e registra o valor realizado
            previsao.realizado = True
            previsao.valor_realizado = valor_transacao
            previsao.transacao_id = transacao.id
            
            # Se houver diferença entre o previsto e realizado, cria nova previsão
            diferenca = valor_original - valor_transacao
            if diferenca != 0:
                nova_previsao = OrcamentoPrevisao(
                    orcamento_id=self.id,
                    data_prevista=data_transacao,
                    valor=diferenca,
                    realizado=False,
                    descricao=f"Ajuste após transação {transacao.id}",
                    categoria_id=self.categoria_id  # Adicionando categoria_id
                )
                db.session.add(nova_previsao)
        else:
            # Cria uma previsão negativa se não existia previsão
            nova_previsao = OrcamentoPrevisao(
                orcamento_id=self.id,
                data_prevista=data_transacao,
                valor=-valor_transacao,
                realizado=False,
                descricao=f"Transação não prevista {transacao.id}",
                categoria_id=self.categoria_id  # Adicionando categoria_id
            )
            db.session.add(nova_previsao)

class OrcamentoLancamento(BaseModel):
    """Modelo para lançamentos específicos de um orçamento com padrões de repetição."""
    __tablename__ = 'orcamento_lancamento'
    
    id = db.Column(db.Integer, primary_key=True)
    orcamento_id = db.Column(db.Integer, db.ForeignKey('orcamento.id'), nullable=False)
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    descricao = db.Column(db.String(200))
    
    # Campos para controle de repetição
    data_inicial = db.Column(db.Date, nullable=False)
    tipo_repeticao = db.Column(db.String(20), nullable=False)
    intervalo_repeticao = db.Column(db.Integer, default=1)
    dia_fixo = db.Column(db.Integer, nullable=True)  # Para repetições mensais
    dia_semana = db.Column(db.Integer, nullable=True)  # 0-6 para repetições semanais
    
    # Relacionamentos
    orcamento = db.relationship('Orcamento', back_populates='lancamentos')

    def gerar_datas_lancamento(self, data_inicio, data_fim):
        """
        Gera todas as datas de lançamento baseadas no padrão de repetição.
        
        Args:
            data_inicio (date): Data inicial do período do orçamento
            data_fim (date): Data final do período do orçamento
            
        Returns:
            list: Lista de datas (date) em que o lançamento deve ocorrer
        """
        from datetime import date, timedelta
        from dateutil.relativedelta import relativedelta
        import calendar
        
        print(f"Gerando datas de lançamento:")
        print(f"- Período do orçamento: {data_inicio} até {data_fim}")
        print(f"- Data inicial do lançamento: {self.data_inicial}")
        print(f"- Tipo repetição: {self.tipo_repeticao}")
        print(f"- Intervalo: {self.intervalo_repeticao}")
        
        datas = []
        data_atual = self.data_inicial
        
        # Validação inicial
        if data_atual > data_fim:
            print("Data inicial do lançamento após data final do orçamento - retornando lista vazia")
            return datas
            
        # Caso único
        if self.tipo_repeticao == 'unico':
            if data_inicio <= self.data_inicial <= data_fim:
                datas.append(self.data_inicial)
            return datas

        # Define um limite máximo de iterações para segurança
        max_iteracoes = 1000
        iteracoes = 0
        
        while data_atual <= data_fim and iteracoes < max_iteracoes:
            iteracoes += 1
            print(f"Iteração {iteracoes}: processando data {data_atual}")
            
            try:
                # Repetição diária
                if self.tipo_repeticao == 'diario':
                    # Adiciona a data se estiver dentro do período
                    if data_inicio <= data_atual <= data_fim:
                        datas.append(data_atual)
                    data_atual += timedelta(days=self.intervalo_repeticao)
                    
                # Repetição semanal
                elif self.tipo_repeticao == 'semanal':
                    if self.dia_semana is not None:
                        if iteracoes == 1:
                            # Se não estiver no dia da semana correto
                            if data_atual.weekday() != self.dia_semana:
                                # Calcula dias até o próximo dia da semana desejado
                                dias_ate_primeiro = (self.dia_semana - data_atual.weekday() + 7) % 7
                                data_atual += timedelta(days=dias_ate_primeiro)
                            
                        # Só adiciona se estiver dentro do período do orçamento
                        if data_inicio <= data_atual <= data_fim:
                            datas.append(data_atual)
                            
                        # Avança para a próxima data apenas se não for a primeira iteração
                        # ou se já estiver no dia da semana correto
                        if iteracoes > 1 or data_atual.weekday() == self.dia_semana:
                            data_atual += timedelta(weeks=self.intervalo_repeticao)
                    else:
                        # Se não tem dia específico
                        if data_inicio <= data_atual <= data_fim:
                            datas.append(data_atual)
                        data_atual += timedelta(weeks=self.intervalo_repeticao)
                        
                # Repetição mensal
                elif self.tipo_repeticao == 'mensal':
                    if self.dia_fixo:
                        if data_inicio <= data_atual <= data_fim:
                            datas.append(data_atual)
                        
                        # Avança para o próximo mês
                        data_atual += relativedelta(months=self.intervalo_repeticao)
                        
                        # Ajusta para o dia fixo, considerando o último dia do mês
                        ultimo_dia = calendar.monthrange(data_atual.year, data_atual.month)[1]
                        dia_efetivo = min(self.dia_fixo, ultimo_dia)
                        data_atual = date(data_atual.year, data_atual.month, dia_efetivo)
                    else:
                        if data_inicio <= data_atual <= data_fim:
                            datas.append(data_atual)
                        
                        # Se não tem dia fixo, mantém o mesmo dia do mês
                        data_atual += relativedelta(months=self.intervalo_repeticao)
                        
                        # Ajusta se o dia não existe no mês
                        ultimo_dia = calendar.monthrange(data_atual.year, data_atual.month)[1]
                        if data_atual.day > ultimo_dia:
                            data_atual = data_atual.replace(day=ultimo_dia)
                
            except Exception as e:
                print(f"Erro ao calcular próxima data: {str(e)}")
                break
                
            if iteracoes == max_iteracoes:
                print(f"Atingido limite máximo de {max_iteracoes} iterações")
                break
        
        # Ordena as datas antes de retornar
        datas_ordenadas = sorted(datas)
        
        print(f"\nGeração de datas concluída. Total de datas: {len(datas_ordenadas)}")
        print("Datas geradas:")
        for data in datas_ordenadas:
            print(f"- {data.strftime('%d/%m/%Y')}")
            
        return datas_ordenadas

    def __repr__(self):
        return f'<OrcamentoLancamento {self.data_inicial} - R${self.valor}>'

class OrcamentoPrevisao(BaseModel):
    """Modelo para previsões de gastos dos orçamentos."""
    __tablename__ = 'orcamento_previsao'
    
    id = db.Column(db.Integer, primary_key=True)
    orcamento_id = db.Column(db.Integer, db.ForeignKey('orcamento.id'), nullable=False)
    data_prevista = db.Column(db.Date, nullable=False)
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    descricao = db.Column(db.String(200))
    realizado = db.Column(db.Boolean, default=False)
    valor_realizado = db.Column(db.Numeric(10, 2), nullable=True)
    transacao_id = db.Column(db.Integer, db.ForeignKey('transacao.id'), nullable=True)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'), nullable=False)

    # Relacionamentos
    orcamento = db.relationship('Orcamento', back_populates='previsoes')
    transacao = db.relationship('Transacao')
    categoria = db.relationship('Categoria')

    def atualizar_com_transacao(self, transacao):
        """Atualiza a previsão baseado em uma transação real."""
        if transacao.categoria_id == self.categoria_id:
            self.realizado = True
            self.valor_realizado = transacao.valor
            self.transacao_id = transacao.id
            return True
        return False
    
    def to_dict(self):
        """Serializa a previsão para um dicionário."""
        return {
            'id': self.id,
            'data_prevista': self.data_prevista.strftime('%Y-%m-%d'),
            'valor': float(self.valor),
            'descricao': self.descricao,
            'categoria': self.categoria.nome if self.categoria else None,
            'tipo': self.orcamento.tipo if self.orcamento else None
        }

class OrcamentoHistorico(BaseModel):
    """Modelo para histórico de execução dos orçamentos."""
    __tablename__ = 'orcamento_historico'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    orcamento_id = db.Column(db.Integer, db.ForeignKey('orcamento.id'), nullable=False)
    mes_referencia = db.Column(db.Date, nullable=False)
    valor_orcado = db.Column(db.Numeric(10, 2), nullable=False)
    valor_realizado = db.Column(db.Numeric(10, 2), nullable=False, default=0)

    # Relacionamento
    orcamento = db.relationship('Orcamento', back_populates='historicos')

    def __repr__(self):
        return f'<OrcamentoHistorico {self.mes_referencia.strftime("%m/%Y")} - R${self.valor_realizado}>'