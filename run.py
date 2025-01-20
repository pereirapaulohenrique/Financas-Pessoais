from app import create_app, db
from flask_migrate import upgrade

app = create_app()

@app.cli.command()
def deploy():
    """Comando de deploy para executar tarefas de configuração."""
    # Aplica as migrações do banco de dados
    upgrade()

if __name__ == '__main__':
    app.run(debug=True)