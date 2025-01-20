from app import db
from app.models.base import BaseModel

class CartaoCredito(BaseModel):
    """Modelo para cartões de crédito."""
    __tablename__ = 'cartao_credito'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    limite = db.Column(db.Float, nullable=False)
    limite_disponivel = db.Column(db.Float, nullable=False, default=0)
    fechamento = db.Column(db.Integer, nullable=False)
    vencimento = db.Column(db.Integer, nullable=False)
    conta_id = db.Column(db.Integer, db.ForeignKey('conta.id'), nullable=False)

    # Relacionamentos
    conta = db.relationship('Conta', back_populates='cartoes')
    transacoes = db.relationship('Transacao', back_populates='cartao')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Inicializa o limite disponível igual ao limite total
        self.limite_disponivel = kwargs.get('limite', 0)

    def calcular_fatura_atual(self):
        """Calcula o valor da fatura atual do cartão."""
        from datetime import datetime
        hoje = datetime.now()
        
        if hoje.day > self.fechamento:
            if hoje.month == 12:
                mes_fatura = 1
                ano_fatura = hoje.year + 1
            else:
                mes_fatura = hoje.month + 1
                ano_fatura = hoje.year
        else:
            mes_fatura = hoje.month
            ano_fatura = hoje.year

        total = 0
        for transacao in self.transacoes:
            if (transacao.deleted_at is None and
                transacao.data.month == mes_fatura and
                transacao.data.year == ano_fatura):
                total += transacao.valor

        return total

    def atualizar_limite_disponivel(self):
        """Atualiza o limite disponível baseado nas transações não pagas."""
        total_usado = 0
        for transacao in self.transacoes:
            if transacao.deleted_at is None and transacao.status == 'aberto':
                total_usado += float(transacao.valor)
        
        self.limite_disponivel = float(self.limite) - total_usado
        return self.limite_disponivel