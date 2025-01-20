from datetime import datetime
from app import db

class BaseModel(db.Model):
    """Modelo base com campos e métodos comuns para todos os modelos."""
    __abstract__ = True

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def save(self):
        """Salva o modelo no banco de dados."""
        try:
            db.session.add(self)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    def delete(self, soft=True):
        """Deleta o modelo do banco de dados.
        
        Args:
            soft (bool): Se True, realiza soft delete. Se False, deleta permanentemente.
        """
        try:
            if soft:
                self.deleted_at = datetime.utcnow()
                db.session.commit()
            else:
                db.session.delete(self)
                db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e

    def update(self, **kwargs):
        """Atualiza os atributos do modelo."""
        try:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            raise e