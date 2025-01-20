from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate  # Adicione esta linha
from config import config

db = SQLAlchemy()
migrate = Migrate()  # Adicione esta linha
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'info'

def create_app(config_name='default'):
    app = Flask(__name__)
    
    # Configuração
    app.config.from_object(config[config_name])
    
    # Inicializar extensões
    db.init_app(app)
    migrate.init_app(app, db)  # Adicione esta linha
    login_manager.init_app(app)
    
    with app.app_context():
        # ... resto do seu código ...
        # Importar e registrar blueprints
        from app.routes import (
            main_bp,
            auth_bp,
            dashboard_bp,
            conta_bp,
            categoria_bp,
            transacao_bp,
            titular_bp,
            orcamento_bp  # Adiciona o import do blueprint de orçamento
        )
        
        app.register_blueprint(main_bp)
        app.register_blueprint(auth_bp)
        app.register_blueprint(dashboard_bp)
        app.register_blueprint(conta_bp)
        app.register_blueprint(categoria_bp)
        app.register_blueprint(transacao_bp)
        app.register_blueprint(titular_bp)
        app.register_blueprint(orcamento_bp)  # Registra o blueprint de orçamento
        
        # Criar todas as tabelas do banco de dados
        db.create_all()
        
        return app