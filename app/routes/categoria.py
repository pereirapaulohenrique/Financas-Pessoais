from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app.models import Categoria, Transacao
from app import db

categoria_bp = Blueprint('categoria', __name__, url_prefix='/categoria')

@categoria_bp.route('/')
@login_required
def listar():
    categorias = Categoria.query.filter_by(deleted_at=None).all()
    return render_template('categoria/listar.html', categorias=categorias)

@categoria_bp.route('/cadastrar', methods=['GET', 'POST'])
@login_required
def cadastrar():
    if request.method == 'POST':
        # Verificar se a requisição é JSON
        if request.is_json:
            data = request.get_json()
            nome = data.get('nome')
        else:
            nome = request.form.get('nome')

        if not nome:
            if request.is_json:
                return jsonify({'success': False, 'error': 'Nome é obrigatório'}), 400
            flash('Nome é obrigatório', 'error')
            return redirect(url_for('categoria.cadastrar'))

        try:
            # Verificar se já existe uma categoria com este nome
            categoria_existente = Categoria.query.filter_by(nome=nome, deleted_at=None).first()
            if categoria_existente:
                if request.is_json:
                    return jsonify({'success': False, 'error': 'Já existe uma categoria com este nome'}), 400
                flash('Já existe uma categoria com este nome', 'error')
                return redirect(url_for('categoria.cadastrar'))

            categoria = Categoria(nome=nome)
            db.session.add(categoria)
            db.session.commit()

            if request.is_json:
                return jsonify({
                    'success': True,
                    'categoria_id': categoria.id,
                    'nome': categoria.nome
                })
                
            flash('Categoria cadastrada com sucesso!', 'success')
            return redirect(url_for('categoria.listar'))
            
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return jsonify({'success': False, 'error': str(e)}), 500
            flash(f'Erro ao cadastrar categoria: {str(e)}', 'error')
            
    return render_template('categoria/cadastrar.html')

@categoria_bp.route('/editar/<int:categoria_id>', methods=['GET', 'POST'])
@login_required
def editar(categoria_id):
    categoria = Categoria.query.get_or_404(categoria_id)
    
    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
            nome = data.get('nome')
        else:
            nome = request.form.get('nome')

        if not nome:
            if request.is_json:
                return jsonify({'success': False, 'error': 'Nome é obrigatório'}), 400
            flash('Nome é obrigatório', 'error')
            return redirect(url_for('categoria.editar', categoria_id=categoria_id))

        try:
            # Verificar se já existe outra categoria com este nome
            categoria_existente = Categoria.query.filter(
                Categoria.nome == nome,
                Categoria.id != categoria_id,
                Categoria.deleted_at == None
            ).first()
            
            if categoria_existente:
                if request.is_json:
                    return jsonify({'success': False, 'error': 'Já existe uma categoria com este nome'}), 400
                flash('Já existe uma categoria com este nome', 'error')
                return redirect(url_for('categoria.editar', categoria_id=categoria_id))

            categoria.nome = nome
            db.session.commit()

            if request.is_json:
                return jsonify({'success': True, 'message': 'Categoria atualizada com sucesso'})
                
            flash('Categoria atualizada com sucesso!', 'success')
            return redirect(url_for('categoria.listar'))
            
        except Exception as e:
            db.session.rollback()
            if request.is_json:
                return jsonify({'success': False, 'error': str(e)}), 500
            flash(f'Erro ao atualizar categoria: {str(e)}', 'error')
    
    return render_template('categoria/editar.html', categoria=categoria)

@categoria_bp.route('/excluir/<int:categoria_id>', methods=['POST'])
@login_required
def excluir(categoria_id):
    try:
        # Verificar se existem transações usando esta categoria
        tem_transacoes = Transacao.query.filter_by(
            categoria_id=categoria_id,
            deleted_at=None
        ).first()
        
        if tem_transacoes:
            if request.is_json:
                return jsonify({
                    'success': False,
                    'error': 'Não é possível excluir uma categoria que possui transações'
                }), 400
            flash('Não é possível excluir uma categoria que possui transações', 'error')
            return redirect(url_for('categoria.listar'))

        categoria = Categoria.query.get_or_404(categoria_id)
        categoria.delete()  # Usando o método de soft delete do BaseModel
        
        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Categoria excluída com sucesso'
            })
            
        flash('Categoria excluída com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        if request.is_json:
            return jsonify({'success': False, 'error': str(e)}), 500
        flash(f'Erro ao excluir categoria: {str(e)}', 'error')
    
    return redirect(url_for('categoria.listar'))

@categoria_bp.route('/ajax/listar', methods=['GET'])
@login_required
def listar_ajax():
    """Endpoint para listar categorias via AJAX."""
    try:
        categorias = Categoria.query.filter_by(deleted_at=None).all()
        return jsonify({
            'success': True,
            'categorias': [{'id': c.id, 'nome': c.nome} for c in categorias]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@categoria_bp.route('/cadastrar_ajax', methods=['POST'])
@login_required
def cadastrar_ajax():
    """Endpoint para cadastrar categoria via AJAX."""
    data = request.get_json()
    
    if not data or 'nome' not in data:
        return jsonify({'success': False, 'error': 'Nome é obrigatório'}), 400
        
    nome = data.get('nome').strip()
    
    if not nome:
        return jsonify({'success': False, 'error': 'Nome é obrigatório'}), 400
        
    try:
        # Verificar se já existe uma categoria com este nome
        categoria_existente = Categoria.query.filter_by(nome=nome, deleted_at=None).first()
        if categoria_existente:
            return jsonify({'success': False, 'error': 'Já existe uma categoria com este nome'}), 400

        categoria = Categoria(nome=nome)
        db.session.add(categoria)
        db.session.commit()

        return jsonify({
            'success': True,
            'categoria_id': categoria.id,
            'nome': categoria.nome
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500