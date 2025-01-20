from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, json
from flask_login import login_required
from sqlalchemy import func, and_, case, or_
from sqlalchemy.orm import joinedload
from app import db
from app.models import Transacao, Conta, OrcamentoPrevisao, Orcamento, Categoria, CartaoCredito  # Adicionado Categoria e CartaoCredito
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import calendar

transacao_bp = Blueprint('transacao', __name__, url_prefix='/transacao')

@transacao_bp.route('/cadastrar', methods=['GET', 'POST'])
@login_required
def cadastrar():
    if request.method == 'POST':
        try:
            tipo_transacao = request.form.get('tipo_transacao')
            data_str = request.form.get('data')
            data = datetime.strptime(data_str, '%Y-%m-%d').date()
            categoria_id = int(request.form.get('categoria'))
            descricao = request.form.get('descricao')
            valor = float(request.form.get('valor', 0))
            lancamento_futuro = request.form.get('lancamento_futuro')
            status = "aberto" if lancamento_futuro else "efetivado"

            if tipo_transacao == 'conta_corrente':
                tipo = request.form.get('tipo')  # "Receita" ou "Despesa"
                conta_id = int(request.form.get('conta'))
                nova_transacao = Transacao(
                    data=data,
                    tipo=tipo,
                    conta_id=conta_id,
                    categoria_id=categoria_id,
                    descricao=descricao,
                    valor=valor,
                    status=status
                )
                db.session.add(nova_transacao)

            elif tipo_transacao == 'cartao_credito':
                cartao_id = int(request.form.get('cartao'))
                num_parcelas = int(request.form.get('num_parcelas', 1))
                cartao = CartaoCredito.query.get(cartao_id)

                # Verificar se há limite disponível para a compra total
                if valor > cartao.limite_disponivel:
                    flash(f'Limite insuficiente. Disponível: R$ {cartao.limite_disponivel:.2f}', 'danger')
                    return redirect(url_for('transacao.cadastrar'))

                # Cálculo das parcelas
                valor_parcela = round(valor / num_parcelas, 2)
                dia_compra = data.day
                mes_compra = data.month
                ano_compra = data.year

                if dia_compra <= cartao.fechamento:
                    mes_primeira_parcela = mes_compra
                    ano_primeira_parcela = ano_compra
                else:
                    mes_primeira_parcela = mes_compra + 1 if mes_compra < 12 else 1
                    ano_primeira_parcela = ano_compra if mes_compra < 12 else ano_compra + 1

                transacoes_criadas = []
                try:
                    for parcela in range(num_parcelas):
                        data_parcela = date(ano_primeira_parcela, mes_primeira_parcela, cartao.vencimento)
                        nova_transacao = Transacao(
                            data=data_parcela,
                            tipo="Despesa de Cartão de Crédito",
                            conta_id=cartao.conta_id,
                            categoria_id=categoria_id,
                            descricao=f"{descricao} (Parcela {parcela + 1}/{num_parcelas})",
                            valor=valor_parcela,
                            status="aberto",
                            cartao_id=cartao_id
                        )
                        db.session.add(nova_transacao)
                        transacoes_criadas.append(nova_transacao)

                        mes_primeira_parcela += 1
                        if mes_primeira_parcela > 12:
                            mes_primeira_parcela = 1
                            ano_primeira_parcela += 1

                    # Atualizar limite disponível do cartão
                    cartao.limite_disponivel -= valor
                    db.session.flush()  # Garante que todas as transações foram criadas antes do commit

                except Exception as e:
                    # Se houver erro, remove todas as transações criadas
                    for transacao in transacoes_criadas:
                        db.session.expunge(transacao)
                    raise e

            db.session.commit()
            flash('Transação cadastrada com sucesso!', 'success')
            return redirect(url_for('transacao.cadastrar'))

        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar transação: {str(e)}', 'danger')
            return redirect(url_for('transacao.cadastrar'))

    # GET request
    contas = Conta.query.filter_by(deleted_at=None).all()
    categorias = Categoria.query.filter_by(deleted_at=None).all()
    cartoes = CartaoCredito.query.filter_by(deleted_at=None).all()
    
    # Atualiza o limite disponível de todos os cartões antes de exibir
    for cartao in cartoes:
        cartao.atualizar_limite_disponivel()
    
    return render_template(
        'transacao/cadastrar.html',
        contas=contas,
        categorias=categorias,
        cartoes=cartoes
    )

@transacao_bp.route('/consultar', methods=['GET'])
@login_required
def consultar():
    # Filtros fornecidos pelo usuário
    filtros = {
        'data_inicio': request.args.get('data_inicio', ''),
        'data_fim': request.args.get('data_fim', ''),
        'tipo': request.args.get('tipo', ''),
        'conta': request.args.get('conta', ''),
        'categoria': request.args.get('categoria', '')
    }

    # Base da query com os relacionamentos necessários
    query = Transacao.query.options(
        joinedload(Transacao.conta),
        joinedload(Transacao.categoria),
        joinedload(Transacao.cartao)
    ).filter_by(deleted_at=None)

    # Aplicar os filtros à query
    if filtros['data_inicio']:
        query = query.filter(Transacao.data >= filtros['data_inicio'])
    if filtros['data_fim']:
        query = query.filter(Transacao.data <= filtros['data_fim'])
    if filtros['tipo']:
        query = query.filter(Transacao.tipo == filtros['tipo'])
    if filtros['conta']:
        query = query.filter(Transacao.conta_id == int(filtros['conta']))
    if filtros['categoria']:
        query = query.filter(Transacao.categoria_id == int(filtros['categoria']))

    # Obter todas as transações ordenadas por data
    transacoes = query.order_by(Transacao.data.desc()).all()

    # Agrupamento de transações por cartão e cálculo do total da fatura
    transacoes_por_cartao = {}
    transacoes_sem_cartao = []

    for transacao in transacoes:
        if transacao.cartao:
            # Chave única para cada fatura (cartão + mês + ano)
            chave_cartao = (
                transacao.cartao.id,
                transacao.cartao.nome,
                transacao.data.strftime('%m'),
                transacao.data.strftime('%Y')
            )

            if chave_cartao not in transacoes_por_cartao:
                # Calcula a data de vencimento da fatura
                data_vencimento = date(
                    int(transacao.data.strftime('%Y')),
                    int(transacao.data.strftime('%m')),
                    transacao.cartao.vencimento
                )
                
                # Determina o status da fatura com base nas transações
                # Se todas as transações estiverem efetivadas, a fatura está efetivada
                status_fatura = "efetivado"
                fatura_id = None
                
                transacoes_por_cartao[chave_cartao] = {
                    'cartao_nome': transacao.cartao.nome,
                    'cartao_id': transacao.cartao.id,
                    'conta_nome': transacao.cartao.conta.nome,
                    'conta_id': transacao.cartao.conta_id,
                    'mes': transacao.data.strftime('%m'),
                    'ano': transacao.data.strftime('%Y'),
                    'data_vencimento': data_vencimento,
                    'transacoes': [],
                    'total_fatura': 0,
                    'status': status_fatura,
                    'fatura_id': fatura_id  # ID da transação que representa a fatura
                }
            
            transacoes_por_cartao[chave_cartao]['transacoes'].append(transacao)
            transacoes_por_cartao[chave_cartao]['total_fatura'] += transacao.valor
            
            # Se alguma transação estiver aberta, a fatura está aberta
            if transacao.status == "aberto":
                transacoes_por_cartao[chave_cartao]['status'] = "aberto"

        else:
            transacoes_sem_cartao.append(transacao)

    # Buscar contas e categorias para os filtros
    contas = Conta.query.filter_by(deleted_at=None).all()
    categorias = Categoria.query.filter_by(deleted_at=None).all()

    return render_template(
        'transacao/consultar.html',
        transacoes_por_cartao=transacoes_por_cartao,
        transacoes_sem_cartao=transacoes_sem_cartao,
        contas=contas,
        categorias=categorias,
        filtros=filtros
    )

@transacao_bp.route('/bulk', methods=['GET', 'POST'])
@login_required
def cadastrar_bulk():
    """Cadastra múltiplas transações de uma vez."""
    if request.method == 'POST':
        try:
            modo = request.form.get('modo')
            transacoes = json.loads(request.form.get('transacoes'))
            
            # Filtrar linhas vazias
            transacoes = [t for t in transacoes if any(cell for cell in t)]
            
            if not transacoes:
                return jsonify({'success': False, 'error': 'Nenhuma transação válida encontrada'})
            
            if len(transacoes) > 20:
                return jsonify({'success': False, 'error': 'Máximo de 20 transações permitido'})

            for transacao_data in transacoes:
                if modo == 'conta':
                    conta = Conta.query.filter_by(nome=transacao_data[2], deleted_at=None).first()
                    categoria = Categoria.query.filter_by(nome=transacao_data[3], deleted_at=None).first()
                    
                    if not conta or not categoria:
                        continue
                        
                    nova_transacao = Transacao(
                        data=datetime.strptime(transacao_data[0], '%Y-%m-%d').date(),
                        tipo=transacao_data[1],
                        conta_id=conta.id,
                        categoria_id=categoria.id,
                        descricao=transacao_data[4],
                        valor=float(transacao_data[5]) if transacao_data[5] else 0,
                        status="aberto" if transacao_data[6] else "efetivado"
                    )
                    db.session.add(nova_transacao)
                
                else:  # modo == 'cartao'
                    cartao = CartaoCredito.query.filter_by(nome=transacao_data[1], deleted_at=None).first()
                    categoria = Categoria.query.filter_by(nome=transacao_data[2], deleted_at=None).first()
                    
                    if not cartao or not categoria:
                        continue
                        
                    data = datetime.strptime(transacao_data[0], '%Y-%m-%d').date()
                    valor = float(transacao_data[4]) if transacao_data[4] else 0
                    num_parcelas = int(transacao_data[5]) if transacao_data[5] else 1
                    
                    # Cálculo das parcelas usando a mesma lógica do cadastro individual
                    dia_compra = data.day
                    mes_compra = data.month
                    ano_compra = data.year
                    
                    if dia_compra <= cartao.fechamento:
                        mes_primeira_parcela = mes_compra
                        ano_primeira_parcela = ano_compra
                    else:
                        mes_primeira_parcela = mes_compra + 1 if mes_compra < 12 else 1
                        ano_primeira_parcela = ano_compra if mes_compra < 12 else ano_compra + 1

                    valor_parcela = round(valor / num_parcelas, 2)

                    for parcela in range(num_parcelas):
                        data_parcela = date(ano_primeira_parcela, mes_primeira_parcela, cartao.vencimento)
                        
                        nova_transacao = Transacao(
                            data=data_parcela,
                            tipo="Despesa de Cartão de Crédito",
                            conta_id=cartao.conta_id,
                            categoria_id=categoria.id,
                            descricao=f"{transacao_data[3]} (Parcela {parcela + 1}/{num_parcelas})",
                            valor=valor_parcela,
                            status="aberto",
                            cartao_id=cartao.id
                        )
                        db.session.add(nova_transacao)

                        mes_primeira_parcela += 1
                        if mes_primeira_parcela > 12:
                            mes_primeira_parcela = 1
                            ano_primeira_parcela += 1

            db.session.commit()
            return jsonify({'success': True})
            
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)})

    # GET: preparar dados para o template
    contas = [{'id': c.id, 'nome': c.nome} for c in Conta.query.filter_by(deleted_at=None).all()]
    categorias = [{'id': c.id, 'nome': c.nome} for c in Categoria.query.filter_by(deleted_at=None).all()]
    cartoes = [{'id': c.id, 'nome': c.nome} for c in CartaoCredito.query.filter_by(deleted_at=None).all()]
    
    return render_template(
        'transacao/cadastrar_bulk.html',
        contas=contas,
        categorias=categorias,
        cartoes=cartoes
    )

@transacao_bp.route('/extrato', methods=['GET'])
@login_required
def extrato():
    """
    Gera o extrato de transações considerando saldos iniciais, transações reais 
    e previsões com lógica de aproximação de datas.
    """
    DIAS_TOLERANCIA = 3

    # Processamento das datas do período
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')

    if not data_inicio or not data_fim:
        hoje = date.today()
        primeiro_dia = date(hoje.year, hoje.month, 1)
        ultimo_dia = date(hoje.year, hoje.month, calendar.monthrange(hoje.year, hoje.month)[1])
        data_inicio = primeiro_dia.strftime('%Y-%m-%d')
        data_fim = ultimo_dia.strftime('%Y-%m-%d')

    data_inicio_date = datetime.strptime(data_inicio, '%Y-%m-%d').date()
    data_fim_date = datetime.strptime(data_fim, '%Y-%m-%d').date()

    # Cálculo do saldo inicial
    saldo_inicial_contas = db.session.query(
        func.sum(Conta.saldo_inicial)
    ).filter_by(deleted_at=None).scalar() or 0

    saldo_acumulado_anterior = db.session.query(
        func.sum(case(
            (and_(
                Transacao.tipo != 'Transferência',
                Transacao.tipo.in_(['Receita', 'Receita Prevista'])
            ), Transacao.valor),
            (and_(
                Transacao.tipo != 'Transferência',
                Transacao.tipo.in_(['Despesa', 'Despesa de Cartão de Crédito', 'Despesa Prevista'])
            ), -Transacao.valor),
            else_=0
        ))
    ).filter(
        Transacao.deleted_at == None,
        Transacao.data < data_inicio_date,
        Transacao.status == 'efetivado',
        Transacao.ignored == False
    ).scalar() or 0

    saldo_inicial_total = float(saldo_inicial_contas) + float(saldo_acumulado_anterior)

    # Dicionário para armazenar valores por data
    timeline = {}

    # Buscar transações reais do período
    transacoes_reais = db.session.query(
        Transacao
    ).filter(
        Transacao.deleted_at == None,
        Transacao.status == 'efetivado',
        Transacao.ignored == False,
        Transacao.data.between(data_inicio_date, data_fim_date)
    ).all()

    # Processar transações reais primeiro
    for transacao in transacoes_reais:
        if transacao.tipo == 'Transferência':
            # Ignorar transferências internas
            continue
            
        data_str = transacao.data.strftime('%Y-%m-%d')
        if data_str not in timeline:
            timeline[data_str] = {
                'data': transacao.data,
                'receita_real': 0,
                'despesa_real': 0,
                'receita_prevista': 0,
                'despesa_prevista': 0,
                'detalhes': {
                    'receita_real': [],
                    'despesa_real': [],
                    'receita_prevista': [],
                    'despesa_prevista': []
                }
            }

        valor = float(transacao.valor)
        if transacao.tipo in ['Receita', 'Receita Prevista']:
            timeline[data_str]['receita_real'] += valor
            timeline[data_str]['detalhes']['receita_real'].append(transacao.to_dict())
        elif transacao.tipo in ['Despesa', 'Despesa de Cartão de Crédito', 'Despesa Prevista']:
            timeline[data_str]['despesa_real'] += valor
            timeline[data_str]['detalhes']['despesa_real'].append(transacao.to_dict())

    # Criar conjunto de IDs de transações já processadas
    transacoes_realizadas_ids = {t.id for t in transacoes_reais}
    previsoes_realizadas_ids = set()

    # Buscar previsões não realizadas
    previsoes = db.session.query(
        OrcamentoPrevisao
    ).join(
        Orcamento,
        and_(
            OrcamentoPrevisao.orcamento_id == Orcamento.id,
            Orcamento.deleted_at == None
        )
    ).filter(
        OrcamentoPrevisao.data_prevista.between(data_inicio_date, data_fim_date),
        OrcamentoPrevisao.deleted_at == None,
        OrcamentoPrevisao.realizado == False,
        or_(
            OrcamentoPrevisao.transacao_id == None,
            ~OrcamentoPrevisao.transacao_id.in_(transacoes_realizadas_ids)
        )
    ).all()

    # Processar previsões não realizadas
    for previsao in previsoes:
        if (previsao.transacao_id in transacoes_realizadas_ids or
            previsao.id in previsoes_realizadas_ids):
            continue

        data_str = previsao.data_prevista.strftime('%Y-%m-%d')
        if data_str not in timeline:
            timeline[data_str] = {
                'data': previsao.data_prevista,
                'receita_real': 0,
                'despesa_real': 0,
                'receita_prevista': 0,
                'despesa_prevista': 0,
                'detalhes': {
                    'receita_real': [],
                    'despesa_real': [],
                    'receita_prevista': [],
                    'despesa_prevista': []
                }
            }

        valor = float(previsao.valor)
        if previsao.orcamento.tipo == 'Receita':
            timeline[data_str]['receita_prevista'] += valor
            timeline[data_str]['detalhes']['receita_prevista'].append(previsao.to_dict())
        else:
            timeline[data_str]['despesa_prevista'] += valor
            timeline[data_str]['detalhes']['despesa_prevista'].append(previsao.to_dict())

        previsoes_realizadas_ids.add(previsao.id)

    # Calcular saldos acumulados
    extrato_ordenado = []
    saldo_acumulado_real = float(saldo_inicial_total)
    saldo_acumulado_projetado = float(saldo_inicial_total)

    for data_str in sorted(timeline.keys()):
        dia = timeline[data_str]
        
        impacto_real = dia['receita_real'] - dia['despesa_real']
        impacto_previsto = dia['receita_prevista'] - dia['despesa_prevista']
        
        saldo_acumulado_real += impacto_real
        saldo_acumulado_projetado = saldo_acumulado_real + impacto_previsto
        
        extrato_ordenado.append({
            'data': dia['data'],
            'receita_real': dia['receita_real'],
            'despesa_real': dia['despesa_real'],
            'receita_prevista': dia['receita_prevista'],
            'despesa_prevista': dia['despesa_prevista'],
            'saldo_real': saldo_acumulado_real,
            'saldo_projetado': saldo_acumulado_projetado,
            'detalhes': dia['detalhes']
        })

    return render_template(
        'transacao/extrato.html',
        extrato=extrato_ordenado,
        saldo_inicial=float(saldo_inicial_total),
        saldo_final=saldo_acumulado_real,
        saldo_projetado=saldo_acumulado_projetado,
        data_inicio=data_inicio,
        data_fim=data_fim
    )
@transacao_bp.route('/relatorios/categoria/<tipo>')
@login_required
def relatorio_categoria(tipo):
    """Gera relatório de transações por categoria (receitas ou despesas)."""
    if tipo not in ['receita', 'despesa']:
        flash('Tipo de relatório inválido', 'error')
        return redirect(url_for('transacao.listar'))
        
    categorias_query = db.session.query(
        Categoria.nome,
        db.func.sum(Transacao.valor).label('total')
    ).join(
        Transacao,
        db.and_(
            Transacao.categoria_id == Categoria.id,
            Transacao.deleted_at == None,
            Transacao.tipo.like(f"{tipo.capitalize()}%")
        )
    ).filter(
        Categoria.deleted_at == None
    ).group_by(
        Categoria.nome
    ).having(
        db.func.sum(Transacao.valor) > 0
    ).order_by(
        db.func.sum(Transacao.valor).desc()
    )

    resultados = {r.nome: float(r.total) for r in categorias_query.all()}
    return jsonify(resultados)

@transacao_bp.route('/relatorios/mensal')
@login_required
def relatorio_mensal():
    """Gera relatório de transações mensais."""
    try:
        query = db.session.query(
            db.func.strftime('%m/%Y', Transacao.data).label('mes_ano'),
            db.func.sum(db.case(
                (Transacao.tipo.in_(['Receita', 'Receita Prevista']), Transacao.valor),
                else_=0
            )).label('receitas'),
            db.func.sum(db.case(
                (Transacao.tipo.in_(['Despesa', 'Despesa Prevista', 'Despesa de Cartão de Crédito']), Transacao.valor),
                else_=0
            )).label('despesas')
        ).filter(
            Transacao.deleted_at == None
        ).group_by(
            'mes_ano'
        ).order_by(
            'mes_ano'
        )

        resultados = {
            r.mes_ano: {
                'receitas': float(r.receitas),
                'despesas': float(r.despesas)
            }
            for r in query.all()
        }
        
        return jsonify(resultados)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@transacao_bp.route('/efetivar/<int:transacao_id>', methods=['POST'])
@login_required
def efetivar(transacao_id):
    """Efetiva uma transação ou uma fatura inteira."""
    try:
        # Verifica se é uma fatura
        if request.form.get('tipo') == 'fatura':
            # Busca todas as transações da fatura
            transacoes = Transacao.query.filter(
                and_(
                    Transacao.cartao_id == transacao_id,
                    Transacao.data == request.form.get('data_fatura'),
                    Transacao.status == 'aberto',
                    Transacao.deleted_at == None
                )
            ).all()
            
            for transacao in transacoes:
                transacao.status = 'efetivado'
                
        else:
            # Efetiva uma única transação
            transacao = Transacao.query.get_or_404(transacao_id)
            
            if transacao.status != 'aberto':
                flash('Apenas transações com status aberto podem ser efetivadas.', 'warning')
                return redirect(url_for('transacao.consultar'))
                
            transacao.status = 'efetivado'
            
        db.session.commit()
        flash('Transação(ões) efetivada(s) com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao efetivar transação(ões): {str(e)}', 'error')
        
    return redirect(url_for('transacao.consultar'))

@transacao_bp.route('/excluir_multiplas', methods=['POST'])
@login_required
def excluir_multiplas():
    """Exclui múltiplas transações selecionadas."""
    try:
        transacoes_ids = request.form.getlist('selecionados')
        
        if not transacoes_ids:
            flash('Nenhuma transação selecionada.', 'warning')
            return redirect(url_for('transacao.consultar'))
            
        transacoes = Transacao.query.filter(
            Transacao.id.in_(transacoes_ids)
        ).all()
        
        for transacao in transacoes:
            transacao.delete()  # Usando o método de soft delete
            
        db.session.commit()
        flash(f'{len(transacoes)} transações excluídas com sucesso!', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir transações: {str(e)}', 'error')
        
    return redirect(url_for('transacao.consultar'))

@transacao_bp.route('/editar/<int:transacao_id>', methods=['GET', 'POST'])
@login_required
def editar(transacao_id):
    """Edita uma transação existente."""
    transacao = Transacao.query.get_or_404(transacao_id)
    
    if request.method == 'POST':
        try:
            data_str = request.form.get('data')
            data = datetime.strptime(data_str, '%Y-%m-%d').date()
            
            transacao.data = data
            transacao.tipo = request.form.get('tipo')
            transacao.conta_id = int(request.form.get('conta'))
            transacao.categoria_id = int(request.form.get('categoria'))
            transacao.descricao = request.form.get('descricao')
            transacao.valor = float(request.form.get('valor', 0))
            
            if request.form.get('lancamento_futuro'):
                transacao.status = 'aberto'
            
            db.session.commit()
            flash('Transação atualizada com sucesso!', 'success')
            return redirect(url_for('transacao.consultar'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar transação: {str(e)}', 'danger')
            return redirect(url_for('transacao.editar', transacao_id=transacao_id))
    
    # GET request
    contas = Conta.query.filter_by(deleted_at=None).all()
    categorias = Categoria.query.filter_by(deleted_at=None).all()
    
    return render_template(
        'transacao/editar.html',
        transacao=transacao,
        contas=contas,
        categorias=categorias
    )

@transacao_bp.route('/importar', methods=['GET', 'POST'])
@login_required
def importar():
    if request.method == 'POST':
        try:
            modo = request.form.get('modo')
            conta_id = request.form.get('conta_id')
            transacoes = json.loads(request.form.get('transacoes'))
            mapeamento = json.loads(request.form.get('mapeamento', '{}'))
            categorias = json.loads(request.form.get('categorias', '[]'))
            
            # Validar conta
            conta = Conta.query.get(conta_id)
            if not conta:
                return jsonify({
                    'success': False,
                    'error': 'Conta não encontrada'
                })
            
            # Validar mapeamento mínimo necessário
            campos_obrigatorios = {
                'conta': ['data', 'descricao', 'valor'],
                'cartao': ['data', 'descricao', 'valor', 'parcelas']
            }
            
            if not all(campo in mapeamento for campo in campos_obrigatorios[modo]):
                return jsonify({
                    'success': False, 
                    'error': f'Mapeamento incompleto. Campos obrigatórios: {", ".join(campos_obrigatorios[modo])}'
                })
            
            # Filtrar linhas vazias
            transacoes = [t for t in transacoes if any(cell for cell in t)]
            
            if not transacoes:
                return jsonify({'success': False, 'error': 'Nenhuma transação válida encontrada'})

            sucessos = []
            erros = []
            
            for idx, transacao_data in enumerate(transacoes):
                try:
                    # Obter categoria da lista de mapeamento
                    categoria_mapeada = next(
                        (cat for cat in categorias if cat['index'] == idx),
                        None
                    )
                    
                    if not categoria_mapeada:
                        erros.append({
                            'linha': idx + 1,
                            'erro': 'Categoria não mapeada para esta transação'
                        })
                        continue
                    
                    categoria = Categoria.query.get(categoria_mapeada['categoria_id'])
                    if not categoria:
                        erros.append({
                            'linha': idx + 1,
                            'erro': 'Categoria inválida'
                        })
                        continue

                    if modo == 'conta':
                        data_str = transacao_data[mapeamento['data']]
                        try:
                            data = datetime.strptime(data_str, '%Y-%m-%d').date()
                        except ValueError:
                            erros.append({
                                'linha': idx + 1,
                                'erro': f'Formato de data inválido: {data_str}. Use AAAA-MM-DD'
                            })
                            continue

                        try:
                            valor = float(transacao_data[mapeamento['valor']])
                        except ValueError:
                            erros.append({
                                'linha': idx + 1,
                                'erro': f'Valor inválido: {transacao_data[mapeamento["valor"]]}'
                            })
                            continue
                            
                        nova_transacao = Transacao(
                            data=data,
                            tipo=transacao_data[mapeamento['tipo']],
                            conta_id=conta.id,
                            categoria_id=categoria.id,
                            descricao=transacao_data[mapeamento['descricao']],
                            valor=valor,
                            status="efetivado"  # Todas as transações CSV são efetivadas
                        )
                        db.session.add(nova_transacao)
                        sucessos.append(idx + 1)
                
                    else:  # modo == 'cartao'
                        try:
                            data = datetime.strptime(transacao_data[mapeamento['data']], '%Y-%m-%d').date()
                            valor = float(transacao_data[mapeamento['valor']])
                            num_parcelas = int(transacao_data[mapeamento['parcelas']])
                            
                            if num_parcelas < 1 or num_parcelas > 24:
                                raise ValueError('Número de parcelas deve estar entre 1 e 24')
                                
                        except (ValueError, TypeError) as e:
                            erros.append({
                                'linha': idx + 1,
                                'erro': f'Erro nos dados: {str(e)}'
                            })
                            continue

                        # Obter cartão associado à conta
                        cartao = CartaoCredito.query.filter_by(
                            conta_id=conta.id,
                            deleted_at=None
                        ).first()
                        
                        if not cartao:
                            erros.append({
                                'linha': idx + 1,
                                'erro': 'Nenhum cartão encontrado para esta conta'
                            })
                            continue

                        valor_parcela = round(valor / num_parcelas, 2)
                        
                        # Lógica de parcelas
                        dia_compra = data.day
                        mes_compra = data.month
                        ano_compra = data.year
                        
                        if dia_compra <= cartao.fechamento:
                            mes_primeira_parcela = mes_compra
                            ano_primeira_parcela = ano_compra
                        else:
                            mes_primeira_parcela = mes_compra + 1 if mes_compra < 12 else 1
                            ano_primeira_parcela = ano_compra if mes_compra < 12 else ano_compra + 1

                        for parcela in range(num_parcelas):
                            data_parcela = date(ano_primeira_parcela, mes_primeira_parcela, cartao.vencimento)
                            
                            nova_transacao = Transacao(
                                data=data_parcela,
                                tipo="Despesa de Cartão de Crédito",
                                conta_id=cartao.conta_id,
                                categoria_id=categoria.id,
                                descricao=f"{transacao_data[mapeamento['descricao']]} (Parcela {parcela + 1}/{num_parcelas})",
                                valor=valor_parcela,
                                status="efetivado",
                                cartao_id=cartao.id
                            )
                            db.session.add(nova_transacao)

                            mes_primeira_parcela += 1
                            if mes_primeira_parcela > 12:
                                mes_primeira_parcela = 1
                                ano_primeira_parcela += 1

                        sucessos.append(idx + 1)
                        
                except Exception as e:
                    erros.append({
                        'linha': idx + 1,
                        'erro': f'Erro ao processar linha: {str(e)}'
                    })
                    continue

            try:
                if sucessos:
                    db.session.commit()
                return jsonify({
                    'success': True,
                    'message': f'Processamento concluído. {len(sucessos)} transações importadas com sucesso.',
                    'sucessos': sucessos,
                    'erros': erros
                })
            except Exception as e:
                db.session.rollback()
                return jsonify({
                    'success': False,
                    'error': f'Erro ao salvar no banco de dados: {str(e)}',
                    'sucessos': sucessos,
                    'erros': erros
                })
            
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': f'Erro no processamento: {str(e)}'
            })

    # GET: retorna dados necessários para o template
    contas = Conta.query.filter_by(deleted_at=None).all()
    categorias = Categoria.query.filter_by(deleted_at=None).all()
    
    return render_template(
        'transacao/importar.html',
        contas=contas,
        categorias=categorias
    )

# Adicione estas rotas ao seu arquivo transacao.py existente

@transacao_bp.route('/transferencia/nova', methods=['GET', 'POST'])
@login_required
def nova_transferencia():
    """Cria uma nova transferência entre contas."""
    if request.method == 'POST':
        try:
            data_str = request.form.get('data')
            data = datetime.strptime(data_str, '%Y-%m-%d').date()
            valor = float(request.form.get('valor', 0))
            conta_origem_id = int(request.form.get('conta_origem'))
            conta_destino_id = int(request.form.get('conta_destino'))
            descricao = request.form.get('descricao', '')
            lancamento_futuro = request.form.get('lancamento_futuro')
            status = "aberto" if lancamento_futuro else "efetivado"

            # Validações
            if conta_origem_id == conta_destino_id:
                flash('Conta de origem e destino não podem ser iguais.', 'danger')
                return redirect(url_for('transacao.nova_transferencia'))

            if valor <= 0:
                flash('O valor da transferência deve ser maior que zero.', 'danger')
                return redirect(url_for('transacao.nova_transferencia'))

            # Cria a transação de saída
            transacao_saida = Transacao(
                data=data,
                tipo="Transferência",
                conta_id=conta_origem_id,
                valor=valor,
                descricao=descricao,
                status=status,
                conta_destino_id=conta_destino_id
            )
            db.session.add(transacao_saida)
            db.session.flush()  # Gera o ID da transação de saída

            # Cria a transação de entrada vinculada
            transacao_entrada = Transacao(
                data=data,
                tipo="Transferência",
                conta_id=conta_destino_id,
                valor=valor,
                descricao=descricao,
                status=status,
                transferencia_id=transacao_saida.id  # Vincula à transação de saída
            )
            db.session.add(transacao_entrada)

            db.session.commit()
            flash('Transferência realizada com sucesso!', 'success')
            return redirect(url_for('transacao.consultar'))

        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao realizar transferência: {str(e)}', 'danger')
            return redirect(url_for('transacao.nova_transferencia'))

    # GET request
    contas = Conta.query.filter_by(deleted_at=None).all()
    return render_template(
        'transacao/transferencia.html',
        contas=contas,
        hoje=date.today()
    )

@transacao_bp.route('/transferencia/<int:id>/efetivar', methods=['POST'])
@login_required
def efetivar_transferencia(id):
    """Efetiva uma transferência pendente."""
    try:
        # Busca a transação de saída
        transacao_saida = Transacao.query.get_or_404(id)
        
        # Busca a transação de entrada vinculada
        transacao_entrada = Transacao.query.filter_by(
            transferencia_id=transacao_saida.id
        ).first()

        if not transacao_entrada:
            flash('Transação de entrada não encontrada.', 'danger')
            return redirect(url_for('transacao.consultar'))

        if transacao_saida.status != 'aberto' or transacao_entrada.status != 'aberto':
            flash('Apenas transferências pendentes podem ser efetivadas.', 'warning')
            return redirect(url_for('transacao.consultar'))

        # Efetiva ambas as transações
        transacao_saida.status = 'efetivado'
        transacao_entrada.status = 'efetivado'
        
        db.session.commit()
        flash('Transferência efetivada com sucesso!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao efetivar transferência: {str(e)}', 'danger')

    return redirect(url_for('transacao.consultar'))

@transacao_bp.route('/transferencia/<int:id>/excluir', methods=['POST'])
@login_required
def excluir_transferencia(id):
    """Exclui (soft delete) uma transferência e sua contraparte."""
    try:
        # Busca a transação de saída
        transacao_saida = Transacao.query.get_or_404(id)
        
        # Busca a transação de entrada vinculada
        transacao_entrada = Transacao.query.filter_by(
            transferencia_id=transacao_saida.id
        ).first()

        if not transacao_entrada:
            flash('Transação de entrada não encontrada.', 'danger')
            return redirect(url_for('transacao.consultar'))

        # Exclui ambas as transações
        now = datetime.now()
        transacao_saida.deleted_at = now
        transacao_entrada.deleted_at = now
        
        db.session.commit()
        flash('Transferência excluída com sucesso!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir transferência: {str(e)}', 'danger')

    return redirect(url_for('transacao.consultar'))

@transacao_bp.route('/<path:transacao_id>/toggle_ignore', methods=['POST'])
@login_required
def toggle_ignore(transacao_id):
    """Alterna o status de ignored de uma transação ou grupo de transações."""
    try:
        data = request.get_json()
        ignored_status = data.get('ignored', False)
        
        # Verifica se é uma fatura ou transação individual
        if isinstance(transacao_id, str) and transacao_id.startswith('fatura_'):
            # Extrai o ID do cartão e a data da fatura
            cartao_id = int(transacao_id.split('_')[1])
            data_fatura = request.args.get('data_fatura')
            
            if not data_fatura:
                return jsonify({
                    'success': False, 
                    'error': 'Data da fatura é obrigatória'
                }), 400
            
            # Busca todas as transações da fatura específica
            transacoes = Transacao.query.filter(
                Transacao.cartao_id == cartao_id,
                Transacao.data == data_fatura,
                Transacao.deleted_at == None
            ).all()
            
            if not transacoes:
                return jsonify({
                    'success': False,
                    'error': 'Nenhuma transação encontrada para esta fatura'
                }), 404
                
            # Atualiza o status de todas as transações
            for transacao in transacoes:
                transacao.ignored = ignored_status
        else:
            # Caso seja uma transação individual
            try:
                transacao_id = int(transacao_id)
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'ID de transação inválido'
                }), 400
                
            transacao = Transacao.query.get_or_404(transacao_id)
            transacao.ignored = ignored_status
        
        db.session.commit()
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500