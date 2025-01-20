from flask import Blueprint, render_template, jsonify
from flask_login import login_required
from app.models import Conta, Transacao, Categoria
from app import db
from datetime import datetime, timedelta
from sqlalchemy import func, case
from sqlalchemy.orm import joinedload

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
@login_required
def index():
    # Data atual e próximos 7 dias
    data_atual = datetime.now().date()
    sete_dias = data_atual + timedelta(days=7)
    
    # Buscar saldos das contas correntes
    saldos_corrente = []
    total_corrente = 0
    for conta in Conta.query.filter(
        Conta.deleted_at == None,
        Conta.tipo.in_(Conta.TIPOS_CONTA_CORRENTE)
    ).all():
        saldo = conta.calcular_saldo()
        saldos_corrente.append({
            'conta': conta.nome,
            'saldo': saldo,
            'tipo': conta.tipo
        })
        total_corrente += saldo

     # Buscar saldos das contas de investimento
    saldos_investimento = []
    total_investimento = 0
    for conta in Conta.query.filter(
        Conta.deleted_at == None,
        Conta.tipo.in_(Conta.TIPOS_CONTA_INVESTIMENTO)
    ).all():
        saldo = conta.calcular_saldo()
        saldos_investimento.append({
            'conta': conta.nome,
            'saldo': saldo,
            'tipo': conta.tipo
        })
        total_investimento += saldo

      # Buscar receitas a receber (apenas contas correntes)
    receitas_receber = Transacao.query.join(
        Conta, Transacao.conta_id == Conta.id
    ).filter(
        Transacao.tipo == 'Receita',
        Transacao.status == 'aberto',
        Transacao.data.between(data_atual, sete_dias),
        Transacao.deleted_at == None,
        Conta.tipo.in_(Conta.TIPOS_CONTA_CORRENTE)
    ).all()

    # Buscar despesas a pagar (apenas contas correntes)
    despesas_pagar = Transacao.query.join(
        Conta, Transacao.conta_id == Conta.id
    ).filter(
        Transacao.tipo == 'Despesa',
        Transacao.status == 'aberto',
        Transacao.data.between(data_atual, sete_dias),
        Transacao.deleted_at == None,
        Conta.tipo.in_(Conta.TIPOS_CONTA_CORRENTE)
    ).all()

    return render_template(
        'dashboard/index.html',
        saldos_corrente=saldos_corrente,
        total_corrente=total_corrente,
        saldos_investimento=saldos_investimento,
        total_investimento=total_investimento,
        total_geral=total_corrente + total_investimento,
        receitas_receber=receitas_receber,
        despesas_pagar=despesas_pagar,
        hoje=data_atual
    )

@dashboard_bp.route('/grafico_receitas')
@login_required
def grafico_receitas():
    receitas_por_categoria = db.session.query(
        Categoria.nome,
        func.sum(Transacao.valor).label('total')
    ).join(
        Transacao,
        Categoria.id == Transacao.categoria_id
    ).filter(
        Transacao.tipo == 'Receita',
        Transacao.deleted_at == None,
        Categoria.deleted_at == None
    ).group_by(
        Categoria.nome
    ).having(
        func.sum(Transacao.valor) > 0
    ).all()

    dados = {categoria: float(total) for categoria, total in receitas_por_categoria}
    return jsonify(dados)

@dashboard_bp.route('/grafico_despesas')
@login_required
def grafico_despesas():
    despesas_por_categoria = db.session.query(
        Categoria.nome,
        func.sum(Transacao.valor).label('total')
    ).join(
        Transacao,
        Categoria.id == Transacao.categoria_id
    ).filter(
        Transacao.tipo.in_(['Despesa', 'Despesa de Cartão de Crédito']),
        Transacao.deleted_at == None,
        Categoria.deleted_at == None
    ).group_by(
        Categoria.nome
    ).having(
        func.sum(Transacao.valor) > 0
    ).all()

    dados = {categoria: float(total) for categoria, total in despesas_por_categoria}
    return jsonify(dados)

@dashboard_bp.route('/grafico_mensal')
@login_required
def grafico_mensal():
    resultados = db.session.query(
        func.strftime('%m/%Y', Transacao.data).label('mes_ano'),
        func.sum(
            case(
                (Transacao.tipo == 'Receita', Transacao.valor),
                else_=0
            )
        ).label('receitas'),
        func.sum(
            case(
                (Transacao.tipo.in_(['Despesa', 'Despesa de Cartão de Crédito']), Transacao.valor),
                else_=0
            )
        ).label('despesas')
    ).filter(
        Transacao.deleted_at == None
    ).group_by(
        'mes_ano'
    ).order_by(
        'mes_ano'
    ).all()

    dados = {
        resultado.mes_ano: {
            'receitas': float(resultado.receitas),
            'despesas': float(resultado.despesas)
        }
        for resultado in resultados
    }

    return jsonify(dados)