from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required
from app.models import Usuario
from app import db
import re
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        usuario = Usuario.query.filter_by(email=email).first()
        
        if usuario and usuario.verificar_senha(senha):
            login_user(usuario)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard.index'))
        
        flash('Email ou senha inválidos.', 'danger')
    
    return render_template('auth/login.html')

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/cadastrar', methods=['GET', 'POST'])
def cadastrar():
    if request.method == 'POST':
        nome_completo = request.form['nome_completo']
        data_nascimento = datetime.strptime(request.form['data_nascimento'], '%Y-%m-%d').date()
        email = request.form['email']
        senha = request.form['senha']
        
        if Usuario.query.filter_by(email=email).first():
            flash('Este email já está em uso.', 'danger')
            return render_template('auth/cadastrar.html')
        
        novo_usuario = Usuario(
            nome_completo=nome_completo,
            data_nascimento=data_nascimento,
            email=email
        )
        novo_usuario.set_senha(senha)
        
        try:
            db.session.add(novo_usuario)
            db.session.commit()
            flash('Cadastro realizado com sucesso!', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('Erro ao realizar cadastro.', 'danger')
            
    return render_template('auth/cadastrar.html')

# Nova rota para cadastro via AJAX
@auth_bp.route('/cadastrar_titular_ajax', methods=['POST'])
def cadastrar_titular_ajax():
    data = request.get_json()
    
    # Validações
    if not data:
        return jsonify({'success': False, 'error': 'Dados inválidos'}), 400
    
    nome_completo = data.get('nome_completo', '').strip()
    
    # Obter a data de nascimento do dicionário 'data'
    data_nascimento = data.get('data_nascimento', '')
    
    # Converter a data de nascimento de string para objeto datetime
    if data_nascimento:
        data_nascimento = datetime.strptime(data_nascimento, '%Y-%m-%d').date()
    
    email = data.get('email', '')
    senha = data.get('senha', '')
    
    # Validar campos obrigatórios
    if not all([nome_completo, data_nascimento, email, senha]):
        return jsonify({'success': False, 'error': 'Todos os campos são obrigatórios'}), 400
    
    # Validar email
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_regex, email):
        return jsonify({'success': False, 'error': 'Email inválido'}), 400
    
    # Verificar se o email já existe
    if Usuario.query.filter_by(email=email).first():
        return jsonify({'success': False, 'error': 'Este email já está em uso'}), 400
    
    # Criar novo usuário
    try:
        novo_usuario = Usuario(
            nome_completo=nome_completo,
            data_nascimento=data_nascimento,
            email=email
        )
        novo_usuario.set_senha(senha)
        
        db.session.add(novo_usuario)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'id': novo_usuario.id,
            'nome_completo': novo_usuario.nome_completo
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500