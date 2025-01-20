from app.routes.main import main_bp
from app.routes.auth import auth_bp
from app.routes.dashboard import dashboard_bp
from app.routes.conta import conta_bp
from app.routes.categoria import categoria_bp
from app.routes.transacao import transacao_bp
from app.routes.titular import titular_bp
from app.routes.orcamento import orcamento_bp

__all__ = [
    'main_bp',
    'auth_bp',
    'dashboard_bp',
    'conta_bp',
    'categoria_bp',
    'transacao_bp',
    'titular_bp',
    'orcamento_bp'
]