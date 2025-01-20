from app import db
from app.models.base import BaseModel

class Transacao(BaseModel):
    __tablename__ = 'transacao'

    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.Date, nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    valor = db.Column(db.Numeric(10, 2), nullable=False)
    descricao = db.Column(db.String(200))
    status = db.Column(db.String(20), default="efetivado")
    ignored = db.Column(db.Boolean, default=False)

    def to_dict(self):
        """Serializa a transação para um dicionário."""
        return {
            'id': self.id,
            'data': self.data.strftime('%Y-%m-%d'),
            'tipo': self.tipo,
            'valor': float(self.valor),
            'descricao': self.descricao,
            'status': self.status,
            'categoria': self.categoria.nome if self.categoria else None,
            'conta': self.conta.nome if self.conta else None
        }

    # Chaves estrangeiras
    conta_id = db.Column(db.Integer, db.ForeignKey('conta.id'), nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey('categoria.id'))
    cartao_id = db.Column(db.Integer, db.ForeignKey('cartao_credito.id'))
    transferencia_id = db.Column(db.Integer, db.ForeignKey('transacao.id', name='fk_transacao_transferencia'))
    conta_destino_id = db.Column(db.Integer, db.ForeignKey('conta.id', name='fk_transacao_conta_destino'))

    # Relacionamentos (mantidos como estão)
    conta = db.relationship('Conta', foreign_keys=[conta_id], back_populates='transacoes')
    conta_destino = db.relationship('Conta', foreign_keys=[conta_destino_id], back_populates='transferencias_recebidas')
    categoria = db.relationship('Categoria', back_populates='transacoes')
    cartao = db.relationship('CartaoCredito', back_populates='transacoes')
    
    transacao_vinculada = db.relationship(
        'Transacao',
        remote_side=[id],
        backref=db.backref('transacao_origem', uselist=False),
        foreign_keys=[transferencia_id]
    )