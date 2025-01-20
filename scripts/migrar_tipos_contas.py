import os
import sys

# Adiciona o diretório raiz do projeto ao PYTHONPATH
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(project_root)

from app import create_app, db
from app.models import Conta
import sqlalchemy as sa

def migrar_tipos_conta():
    print("Iniciando migração dos tipos de conta...")
    
    # Primeiro, vamos ver quais tipos existem no banco
    inspector = sa.inspect(db.engine)
    with db.engine.connect() as conn:
        # Usar text() para SQL puro
        result = conn.execute(sa.text('SELECT DISTINCT tipo FROM conta'))
        tipos_existentes = [row[0] for row in result]
    
    print("\nTipos de conta encontrados no banco:")
    for tipo in tipos_existentes:
        print(f"- {tipo}")
    
    # Criar mapeamento dos tipos antigos para os novos
    mapeamento_tipos = {
        # Tipos de conta corrente
        'conta corrente': Conta.TIPO_CONTA_CORRENTE,
        'corrente': Conta.TIPO_CONTA_CORRENTE,
        'salario': Conta.TIPO_CONTA_SALARIO,
        'salário': Conta.TIPO_CONTA_SALARIO,
        
        # Tipos de investimento
        'poupanca': Conta.TIPO_POUPANCA,
        'poupança': Conta.TIPO_POUPANCA,
        'investimento': Conta.TIPO_INVESTIMENTO,
        'conta de investimento': Conta.TIPO_INVESTIMENTO,  # Adicionado este tipo
    }

    # Perguntar se quer prosseguir
    resposta = input("\nDeseja prosseguir com a migração? (s/n): ")
    if resposta.lower() != 's':
        print("Migração cancelada.")
        return

    try:
        # Buscar todas as contas (incluindo as deletadas)
        contas = Conta.query.all()
        total_contas = len(contas)
        print(f"\nEncontradas {total_contas} contas para migração")

        # Contador para contas atualizadas
        contas_atualizadas = 0
        contas_nao_mapeadas = []

        for conta in contas:
            tipo_antigo = conta.tipo.lower()
            novo_tipo = mapeamento_tipos.get(tipo_antigo)

            if novo_tipo:
                print(f"\nAtualizando conta {conta.id} - {conta.nome}")
                print(f"Tipo antigo: {tipo_antigo}")
                print(f"Novo tipo: {novo_tipo}")
                
                conta.tipo = novo_tipo
                contas_atualizadas += 1
            else:
                contas_nao_mapeadas.append({
                    'id': conta.id,
                    'nome': conta.nome,
                    'tipo': tipo_antigo
                })

        if contas_nao_mapeadas:
            print("\nAVISO: As seguintes contas não puderam ser mapeadas:")
            for conta in contas_nao_mapeadas:
                print(f"- ID: {conta['id']}, Nome: {conta['nome']}, Tipo: {conta['tipo']}")
            
            continuar = input("\nDeseja continuar mesmo assim? (s/n): ")
            if continuar.lower() != 's':
                print("Migração cancelada.")
                db.session.rollback()
                return

        # Commit das alterações
        db.session.commit()
        print(f"\nMigração concluída!")
        print(f"Total de contas atualizadas: {contas_atualizadas} de {total_contas}")

    except Exception as e:
        print(f"Erro durante a migração: {str(e)}")
        db.session.rollback()
        raise e

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        migrar_tipos_conta()