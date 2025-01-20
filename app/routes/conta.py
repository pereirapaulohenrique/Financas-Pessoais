from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.models import Conta, CartaoCredito, Usuario
from app import db

conta_bp = Blueprint('conta', __name__, url_prefix='/conta')

@conta_bp.route('/')
@login_required
def listar():
    contas = Conta.query.filter_by(deleted_at=None).all()
    usuarios = Usuario.query.filter_by(deleted_at=None).all()  # Adicionado query de usuários
    return render_template('conta/listar.html', contas=contas, usuarios=usuarios)

@conta_bp.route('/cadastrar', methods=['GET', 'POST'])
@login_required
def cadastrar():
    if request.method == 'POST':
        try:
            # Dados da Conta
            nome = request.form['nome']
            tipo_conta = request.form['tipo_conta']
            titular_id = request.form['titular']
            saldo_inicial = float(request.form.get('saldo_inicial', '0'))  # Novo campo
            
            # Criar a Conta
            nova_conta = Conta(
                nome=nome,
                tipo=tipo_conta,
                titular_id=titular_id,
                saldo_inicial=saldo_inicial  # Adicionado saldo inicial
            )
            db.session.add(nova_conta)
            db.session.flush()

            # Cartões de Crédito
            num_cartoes = int(request.form.get('num_cartoes', '0'))
            
            for i in range(num_cartoes):
                nome_cartao = request.form[f'cartao_nome_{i}']
                limite = float(request.form[f'cartao_limite_{i}'])
                fechamento = int(request.form[f'cartao_fechamento_{i}'])
                vencimento = int(request.form[f'cartao_vencimento_{i}'])

                novo_cartao = CartaoCredito(
                    nome=nome_cartao,
                    limite=limite,
                    fechamento=fechamento,
                    vencimento=vencimento,
                    conta_id=nova_conta.id
                )
                db.session.add(novo_cartao)

            db.session.commit()
            flash("Conta cadastrada com sucesso!", "success")
            
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao cadastrar conta: {str(e)}", "danger")
            
        return redirect(url_for('conta.listar'))

    usuarios = Usuario.query.filter_by(deleted_at=None).all()
    return render_template('conta/cadastrar.html', usuarios=usuarios)

@conta_bp.route('/editar/<int:conta_id>', methods=['GET', 'POST'])
@login_required
def editar(conta_id):
    conta = Conta.query.get_or_404(conta_id)
    
    if request.method == 'POST':
        try:
            conta.nome = request.form['nome']
            conta.tipo = request.form['tipo_conta']
            conta.saldo_inicial = float(request.form['saldo_inicial'])
            
            # Atualizar cartões existentes
            cartao_ids = request.form.getlist('cartao_ids[]')
            cartao_nomes = request.form.getlist('cartao_nome[]')
            cartao_limites = request.form.getlist('cartao_limite[]')
            cartao_fechamentos = request.form.getlist('cartao_fechamento[]')
            cartao_vencimentos = request.form.getlist('cartao_vencimento[]')
            
            for i, cartao_id in enumerate(cartao_ids):
                cartao = CartaoCredito.query.get(cartao_id)
                if cartao and cartao.conta_id == conta.id:
                    cartao.nome = cartao_nomes[i]
                    cartao.limite = float(cartao_limites[i])
                    cartao.fechamento = int(cartao_fechamentos[i])
                    cartao.vencimento = int(cartao_vencimentos[i])
            
            # Adicionar novos cartões
            novo_cartao_nomes = request.form.getlist('novo_cartao_nome[]')
            novo_cartao_limites = request.form.getlist('novo_cartao_limite[]')
            novo_cartao_fechamentos = request.form.getlist('novo_cartao_fechamento[]')
            novo_cartao_vencimentos = request.form.getlist('novo_cartao_vencimento[]')
            
            for i in range(len(novo_cartao_nomes)):
                novo_cartao = CartaoCredito(
                    nome=novo_cartao_nomes[i],
                    limite=float(novo_cartao_limites[i]),
                    fechamento=int(novo_cartao_fechamentos[i]),
                    vencimento=int(novo_cartao_vencimentos[i]),
                    conta_id=conta.id
                )
                db.session.add(novo_cartao)
            
            db.session.commit()
            flash('Conta atualizada com sucesso!', 'success')
            return redirect(url_for('conta.listar'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar conta: {str(e)}', 'danger')
            
    return render_template('conta/editar.html', conta=conta)

@conta_bp.route('/excluir/<int:conta_id>', methods=['POST'])
@login_required
def excluir(conta_id):
    conta = Conta.query.get_or_404(conta_id)
    
    try:
        conta.delete()  # Usando o método de soft delete do BaseModel
        flash('Conta excluída com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro ao excluir conta: {str(e)}', 'danger')
    
    return redirect(url_for('conta.listar'))

@conta_bp.route('/atualizar_saldo_inicial/<int:conta_id>', methods=['POST'])
@login_required
def atualizar_saldo_inicial(conta_id):
    try:
        conta = Conta.query.get_or_404(conta_id)
        novo_saldo = float(request.form.get('saldo_inicial', 0))
        
        conta.saldo_inicial = novo_saldo
        db.session.commit()
        
        flash('Saldo inicial atualizado com sucesso!', 'success')
    except ValueError:
        flash('Valor inválido para saldo inicial', 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao atualizar saldo inicial: {str(e)}', 'danger')
    
    return redirect(url_for('conta.listar'))