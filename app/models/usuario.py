from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import db, login_manager
from app.models.base import BaseModel

class Usuario(UserMixin, BaseModel):
    """Modelo para usuários do sistema."""
    __tablename__ = 'usuario'

    id = db.Column(db.Integer, primary_key=True)
    nome_completo = db.Column(db.String(100), nullable=False)
    data_nascimento = db.Column(db.Date, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    
    # Relacionamento com Conta usando back_populates
    contas = db.relationship('Conta', back_populates='titular', lazy=True,
                           foreign_keys='Conta.titular_id')

    def set_senha(self, senha):
        """Define a senha do usuário."""
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        """Verifica se a senha está correta."""
        return check_password_hash(self.senha_hash, senha)

    @staticmethod
    @login_manager.user_loader
    def load_user(id):
        """Carrega um usuário pelo ID para o Flask-Login."""
        return Usuario.query.get(int(id))