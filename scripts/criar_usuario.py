from app import create_app, db
from app.models import Usuario
from datetime import datetime

app = create_app()
with app.app_context():
    # Criar um usuário admin
    admin = Usuario(
        nome_completo="Paulo Henrique Pereira",
        email="pereirapaulohenrique90@gmail.com",
        data_nascimento=datetime.strptime("1990-12-18", "%Y-%m-%d").date()
    )
    admin.set_senha("30102021")  # Define a senha
    
    try:
        db.session.add(admin)
        db.session.commit()
        print("Usuário admin criado com sucesso!")
        print("Email: admin@admin.com")
        print("Senha: admin123")
    except Exception as e:
        db.session.rollback()
        print(f"Erro ao criar usuário: {str(e)}")