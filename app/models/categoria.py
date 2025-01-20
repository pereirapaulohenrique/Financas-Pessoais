from app import db
from app.models.base import BaseModel

class Categoria(BaseModel):
    __tablename__ = 'categoria'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)

    # Apenas este relacionamento, sem backref
    transacoes = db.relationship('Transacao', back_populates='categoria', lazy=True)
    orcamentos = db.relationship('Orcamento', back_populates='categoria')

    def total_por_tipo(self, tipo, inicio=None, fim=None):
        """Calcula o total de transações por tipo em um período."""
        query = self.transacoes.filter_by(tipo=tipo, deleted_at=None)
        
        if inicio:
            query = query.filter(Transacao.data >= inicio)
        if fim:
            query = query.filter(Transacao.data <= fim)
            
        return sum(t.valor for t in query)