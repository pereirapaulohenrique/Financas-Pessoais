from datetime import datetime
from app import db

class Conta(db.Model):
    __tablename__ = 'conta'
    
    # Constantes para tipos de conta
    TIPO_CONTA_CORRENTE = 'conta_corrente'
    TIPO_CONTA_SALARIO = 'conta_salario'
    TIPO_POUPANCA = 'poupanca'
    TIPO_INVESTIMENTO = 'investimento'
    
    TIPOS_CONTA = [
        (TIPO_CONTA_CORRENTE, 'Conta Corrente'),
        (TIPO_CONTA_SALARIO, 'Conta Salário'),
        (TIPO_POUPANCA, 'Poupança'),
        (TIPO_INVESTIMENTO, 'Investimento')
    ]
    
    # Tipos de conta que afetam orçamento e extrato
    TIPOS_CONTA_CORRENTE = [TIPO_CONTA_CORRENTE, TIPO_CONTA_SALARIO]
    
    # Tipos de conta de investimento
    TIPOS_CONTA_INVESTIMENTO = [TIPO_POUPANCA, TIPO_INVESTIMENTO]
    
    # Colunas do modelo
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    saldo = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    saldo_inicial = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    titular_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime)

    # Relacionamentos
    titular = db.relationship('Usuario', back_populates='contas')
    cartoes = db.relationship('CartaoCredito', back_populates='conta', lazy=True)
    
    transacoes = db.relationship(
        'Transacao',
        foreign_keys='Transacao.conta_id',
        back_populates='conta',
        lazy=True
    )

    transferencias_recebidas = db.relationship(
        'Transacao',
        foreign_keys='Transacao.conta_destino_id',
        back_populates='conta_destino',
        lazy=True
    )

    def __init__(self, **kwargs):
        saldo_inicial = kwargs.pop('saldo_inicial', 0)
        super().__init__(**kwargs)
        self.saldo_inicial = saldo_inicial
        self.saldo = saldo_inicial

    @property
    def afeta_orcamento(self):
        """Retorna True se a conta deve ser considerada em orçamentos e extratos."""
        return self.tipo in self.TIPOS_CONTA_CORRENTE

    @property
    def eh_investimento(self):
        """Retorna True se a conta é do tipo investimento/poupança."""
        return self.tipo in self.TIPOS_CONTA_INVESTIMENTO

    def calcular_saldo_real(self):
        """
        Calcula o saldo real da conta (movimentações sem considerar o saldo inicial).
        
        Returns:
            float: O saldo real da conta (saldo atual - saldo inicial)
        """
        saldo_real = self.saldo - self.saldo_inicial
        return round(float(saldo_real), 2)

    def calcular_saldo(self):
        """
        Calcula o saldo atual da conta considerando todas as transações efetivadas.
        
        Returns:
            float: O saldo atual da conta
        """
        saldo_total = float(self.saldo_inicial)
        
        # Soma todas as transações não deletadas e efetivadas
        for transacao in self.transacoes:
            if transacao.deleted_at is None and transacao.status == 'efetivado' and not transacao.ignored:
                if transacao.tipo in ['Receita', 'Receita Prevista']:
                    saldo_total += float(transacao.valor)
                elif transacao.tipo in ['Despesa', 'Despesa de Cartão de Crédito', 'Despesa Prevista']:
                    saldo_total -= float(transacao.valor)
                elif transacao.tipo == 'Transferência':
                    if transacao.conta_destino_id:  # É uma transferência de saída
                        saldo_total -= float(transacao.valor)
                    elif transacao.transferencia_id:  # É uma transferência de entrada
                        saldo_total += float(transacao.valor)
        
        return round(saldo_total, 2)

    def delete(self):
        """Realiza soft delete da conta."""
        self.deleted_at = datetime.utcnow()

    def __repr__(self):
        return f'<Conta {self.nome}>'