from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.models import Usuario, Conta
from app import db
from datetime import datetime

titular_bp = Blueprint('titular', __name__, url_prefix='/titular')

@titular_bp.route('/')
@login_required
def listar():
    titulares = Usuario.query.filter_by(deleted_at=None).all()
    return render_template('titular/listar.html', titulares=titulares)

@titular_bp.route('/<int:titular_id>')
@login_required
def obter_titular(titular_id):
    titular = Usuario.query.get_or_404(titular_id)
    return jsonify({
        'nome_completo': titular.nome_completo,
        'email': titular.email,
        'data_nascimento': titular.data_nascimento.strftime('%Y-%m-%d')
    })

@titular_bp.route('/cadastrar', methods=['POST'])
@login_required
def cadastrar():
    try:
        dados = request.get_json()
        
        # Verificar se e-mail já existe
        if Usuario.query.filter_by(email=dados['email'], deleted_at=None).first():
            return jsonify({'success': False, 'error': 'E-mail já cadastrado'})
        
        novo_titular = Usuario(
            nome_completo=dados['nome_completo'],
            email=dados['email'],
            data_nascimento=datetime.strptime(dados['data_nascimento'], '%Y-%m-%d').date()
        )
        novo_titular.set_senha(dados['senha'])
        
        db.session.add(novo_titular)
        db.session.commit()
        
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@titular_bp.route('/<int:titular_id>', methods=['PUT'])
@login_required
def atualizar(titular_id):
    try:
        titular = Usuario.query.get_or_404(titular_id)
        dados = request.get_json()
        
        # Verificar se e-mail já existe
        email_existente = Usuario.query.filter_by(
            email=dados['email'], 
            deleted_at=None
        ).filter(Usuario.id != titular_id).first()
        
        if email_existente:
            return jsonify({'success': False, 'error': 'E-mail já cadastrado'})
        
        titular.nome_completo = dados['nome_completo']
        titular.email = dados['email']
        titular.data_nascimento = datetime.strptime(dados['data_nascimento'], '%Y-%m-%d').date()
        
        if dados.get('senha'):
            titular.set_senha(dados['senha'])
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@titular_bp.route('/<int:titular_id>', methods=['DELETE'])
@login_required
def excluir(titular_id):
    try:
        titular = Usuario.query.get_or_404(titular_id)
        
        # Verificar se tem contas vinculadas
        contas = Conta.query.filter_by(titular_id=titular_id, deleted_at=None).all()
        
        # Excluir contas vinculadas (soft delete)
        for conta in contas:
            conta.delete()
        
        # Excluir titular (soft delete)
        titular.delete()
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})