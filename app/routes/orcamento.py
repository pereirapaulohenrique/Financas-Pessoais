from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required
from app import db
from app.models import (
    Orcamento, 
    Categoria, 
    OrcamentoHistorico, 
    OrcamentoPrevisao,
    OrcamentoLancamento,
    TipoRepeticao,
    Transacao
)
from datetime import datetime, date
from sqlalchemy import func, case, and_  # Adicionando case e and_
from sqlalchemy.orm import aliased
import calendar
from dateutil.relativedelta import relativedelta
import json

orcamento_bp = Blueprint('orcamento', __name__, url_prefix='/orcamento')

@orcamento_bp.route('/')
@login_required
def index():
    """Lista todos os orçamentos ativos."""
    # Configuração das datas do filtro
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    hoje = date.today()
    
    # Se não houver datas nos parâmetros, usar o mês atual
    if not data_inicio or not data_fim:
        hoje = date.today()
        primeiro_dia = date(hoje.year, hoje.month, 1)
        ultimo_dia = date(hoje.year, hoje.month, calendar.monthrange(hoje.year, hoje.month)[1])
        data_inicio = primeiro_dia.strftime('%Y-%m-%d')
        data_fim = ultimo_dia.strftime('%Y-%m-%d')

    # Query base
    query = db.session.query(
        Orcamento,
        Categoria.nome.label('categoria_nome'),
        func.coalesce(func.sum(case(
            (Transacao.tipo == Orcamento.tipo, Transacao.valor),
            else_=0
        )), 0).label('valor_realizado')
    ).join(
        Categoria, Orcamento.categoria_id == Categoria.id
    ).outerjoin(
        Transacao,
        db.and_(
            Transacao.categoria_id == Orcamento.categoria_id,
            Transacao.data.between(data_inicio, data_fim),
            Transacao.tipo == Orcamento.tipo,
            Transacao.deleted_at == None
        )
    ).filter(
        Orcamento.deleted_at == None
    )

    # Aplicar filtros de data
    query = query.filter(
        Orcamento.data_inicio <= data_fim,
        Orcamento.data_fim >= data_inicio
    )

    orcamentos = query.group_by(
        Orcamento.id,
        Categoria.nome
    ).all()

    # Função auxiliar para calcular valor proporcional ao período
    def calcular_valor_periodo(orcamento, data_inicio_filtro, data_fim_filtro):
        """Calcula o valor do orçamento para o período especificado baseado nos lançamentos."""
        # Converter strings para date
        if isinstance(data_inicio_filtro, str):
            data_inicio_filtro = datetime.strptime(data_inicio_filtro, '%Y-%m-%d').date()
        if isinstance(data_fim_filtro, str):
            data_fim_filtro = datetime.strptime(data_fim_filtro, '%Y-%m-%d').date()

        valor_total = 0
        
        # Para cada lançamento do orçamento
        for lancamento in orcamento.lancamentos:
            if lancamento.deleted_at:
                continue
                
            # Gerar todas as datas de ocorrência do lançamento
            datas_lancamento = lancamento.gerar_datas_lancamento(
                max(orcamento.data_inicio, data_inicio_filtro),
                min(orcamento.data_fim, data_fim_filtro)
            )
            
            # Somar o valor para cada data dentro do período
            valor_total += float(lancamento.valor) * len(datas_lancamento)
        
        return valor_total

    # Inicializar totalizadores
    orcamentos_formatados = []
    orcamento_receitas = 0
    orcamento_despesas = 0
    total_recebido = 0
    total_gasto = 0
    categorias_limite = 0

    # Processar orçamentos
    for orcamento, cat_nome, valor_realizado in orcamentos:
        valor_orcado = calcular_valor_periodo(orcamento, data_inicio, data_fim)
        valor_realizado = float(valor_realizado or 0)
        
        # Acumular totais
        if orcamento.tipo == 'Receita':
            orcamento_receitas += valor_orcado
            total_recebido += valor_realizado
        else:  # Despesa
            orcamento_despesas += valor_orcado
            total_gasto += valor_realizado
            # Contar apenas despesas no limite
            if valor_orcado > 0 and (valor_realizado / valor_orcado) >= 0.75:
                categorias_limite += 1

        # Formatar dados para o template
        orcamentos_formatados.append({
            'id': orcamento.id,
            'categoria': cat_nome,
            'tipo': orcamento.tipo,
            'valor_orcado': valor_orcado,
            'valor_realizado': valor_realizado,
            'valor_restante': valor_orcado - valor_realizado,
            'percentual': round((valor_realizado / valor_orcado * 100), 1) if valor_orcado > 0 else 0
        })

    # Calcular economia potencial (apenas para despesas)
    economia_potencial = orcamento_despesas - total_gasto if orcamento_despesas > total_gasto else 0

    # Estatísticas para o template
    stats = {
        'orcamento_receitas': orcamento_receitas,
        'orcamento_despesas': orcamento_despesas,
        'total_recebido': total_recebido,
        'total_gasto': total_gasto,
        'categorias_limite': categorias_limite,
        'economia_potencial': economia_potencial
    }

    return render_template(
        'orcamento/index.html',
        orcamentos=orcamentos_formatados,
        stats=stats,
        categorias=Categoria.query.filter_by(deleted_at=None).all(),
        tipos_repeticao=TipoRepeticao.choices(),
        filtros={
            'data_inicio': data_inicio,
            'data_fim': data_fim
        }
    )

@orcamento_bp.route('/<int:id>', methods=['GET'])
@login_required
def get_orcamento(id):
    """Retorna dados de um orçamento específico com seus lançamentos."""
    orcamento = Orcamento.query.get_or_404(id)
    return jsonify({
        'id': orcamento.id,
        'categoria_id': orcamento.categoria_id,
        'valor_total': float(orcamento.valor_total),
        'tipo': orcamento.tipo,
        'data_inicio': orcamento.data_inicio.strftime('%Y-%m-%d'),
        'data_fim': orcamento.data_fim.strftime('%Y-%m-%d'),
        'lancamentos': [{
        'data_inicial': lancamento.data_inicial.strftime('%Y-%m-%d'),
        'valor': float(lancamento.valor),
        'descricao': lancamento.descricao,
        'tipo_repeticao': lancamento.tipo_repeticao,
        'intervalo_repeticao': lancamento.intervalo_repeticao,
        'dia_fixo': lancamento.dia_fixo,
        'dia_semana': lancamento.dia_semana,
        # Adicionar campo para mostrar todas as datas calculadas
        'datas_ocorrencia': [
            data.strftime('%Y-%m-%d') 
            for data in lancamento.gerar_datas_lancamento(
                orcamento.data_inicio, 
                orcamento.data_fim
            )
        ]
    } for lancamento in orcamento.lancamentos if not lancamento.deleted_at]
    })

@orcamento_bp.route('/salvar', methods=['POST'])
@login_required
def salvar():
    """Salva ou atualiza um orçamento com lançamentos específicos."""
    try:
        print("=== INÍCIO DO PROCESSO DE SALVAMENTO ===")
        print(f"Timestamp: {datetime.now()}")
        
        # Obter e validar dados básicos do orçamento
        orcamento_id = request.form.get('id')
        categoria_id = request.form.get('categoria')
        tipo = request.form.get('tipo')
        
        print(f"Dados básicos recebidos:")
        print(f"- ID: {orcamento_id}")
        print(f"- Categoria: {categoria_id}")
        print(f"- Tipo: {tipo}")

        # Validações básicas
        if not categoria_id or not tipo:
            return jsonify({
                'success': False,
                'error': 'Categoria e tipo são obrigatórios'
            }), 400

        if tipo not in ['Receita', 'Despesa']:
            return jsonify({
                'success': False,
                'error': 'Tipo inválido'
            }), 400
        
        # Processar datas
        print("Processando datas...")
        try:
            data_inicio = datetime.strptime(request.form.get('data_inicio'), '%Y-%m-%d').date()
            data_fim = datetime.strptime(request.form.get('data_fim'), '%Y-%m-%d').date()
            print(f"Datas processadas: {data_inicio} até {data_fim}")
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': 'Formato de data inválido'
            }), 400
        
        # Validar datas
        if data_fim < data_inicio:
            print("Erro: Data final menor que inicial")
            return jsonify({
                'success': False,
                'error': 'Data final deve ser maior que a data inicial'
            }), 400

        # Validar período máximo
        diferenca_dias = (data_fim - data_inicio).days
        if diferenca_dias > 366:  # Máximo de 1 ano
            return jsonify({
                'success': False,
                'error': 'O período máximo permitido é de 1 ano'
            }), 400

        print("Iniciando transação do banco de dados...")
        
        # Processar orçamento existente ou criar novo
        if orcamento_id and orcamento_id != 'null':
            print(f"Buscando orçamento existente ID: {orcamento_id}")
            orcamento = Orcamento.query.get_or_404(int(orcamento_id))
            print("Removendo lançamentos existentes...")
            for lancamento in orcamento.lancamentos:
                db.session.delete(lancamento)
        else:
            print("Criando novo orçamento")
            orcamento = Orcamento()

        # Atualizar dados básicos do orçamento
        print("Atualizando dados básicos do orçamento...")
        orcamento.categoria_id = int(categoria_id)
        orcamento.tipo = tipo
        orcamento.data_inicio = data_inicio
        orcamento.data_fim = data_fim
        
        # Processar lançamentos
        print("Iniciando processamento dos lançamentos...")
        lancamentos_raw = request.form.get('lancamentos', '[]')
        print(f"Dados brutos dos lançamentos: {lancamentos_raw[:200]}...")
        
        try:
            lancamentos_data = json.loads(lancamentos_raw)
        except json.JSONDecodeError:
            return jsonify({
                'success': False,
                'error': 'Formato inválido dos lançamentos'
            }), 400

        print(f"Número de lançamentos a processar: {len(lancamentos_data)}")
        
        if not lancamentos_data:
            return jsonify({
                'success': False,
                'error': 'É necessário pelo menos um lançamento'
            }), 400

        if len(lancamentos_data) > 20:  # Limite máximo de lançamentos
            return jsonify({
                'success': False,
                'error': 'Número máximo de lançamentos excedido (20)'
            }), 400
        
        valor_total = 0
        
        for idx, lancamento_data in enumerate(lancamentos_data, 1):
            print(f"\nProcessando lançamento {idx}/{len(lancamentos_data)}")
            print(f"Dados do lançamento: {lancamento_data}")
            
            try:
                # Validar campos obrigatórios
                campos_obrigatorios = ['data_inicial', 'tipo_repeticao', 'intervalo_repeticao', 'valor']
                for campo in campos_obrigatorios:
                    if campo not in lancamento_data:
                        raise KeyError(f'Campo obrigatório ausente: {campo}')

                data_inicial = datetime.strptime(lancamento_data['data_inicial'], '%Y-%m-%d').date()
                valor = float(lancamento_data['valor'])
                tipo_repeticao = lancamento_data['tipo_repeticao']
                intervalo_repeticao = int(lancamento_data['intervalo_repeticao'])

                # Validações adicionais
                if valor <= 0:
                    return jsonify({
                        'success': False,
                        'error': f'Valor deve ser maior que zero no lançamento {idx}'
                    }), 400

                if intervalo_repeticao < 1:
                    return jsonify({
                        'success': False,
                        'error': f'Intervalo de repetição deve ser maior que zero no lançamento {idx}'
                    }), 400

                if tipo_repeticao not in ['unico', 'diario', 'semanal', 'mensal']:
                    return jsonify({
                        'success': False,
                        'error': f'Tipo de repetição inválido no lançamento {idx}'
                    }), 400
                
                print(f"Criando objeto OrcamentoLancamento...")
                lancamento = OrcamentoLancamento(
                    orcamento=orcamento,
                    data_inicial=data_inicial,
                    valor=valor,
                    descricao=lancamento_data.get('descricao', ''),
                    tipo_repeticao=tipo_repeticao,
                    intervalo_repeticao=intervalo_repeticao
                )
                
                print("Processando campos específicos...")
                if tipo_repeticao == 'mensal' and 'dia_fixo' in lancamento_data:
                    dia_fixo = lancamento_data['dia_fixo']
                    if dia_fixo:
                        dia_fixo = int(dia_fixo)
                        if not (1 <= dia_fixo <= 31):
                            return jsonify({
                                'success': False,
                                'error': f'Dia fixo deve estar entre 1 e 31 no lançamento {idx}'
                            }), 400
                        lancamento.dia_fixo = dia_fixo
                
                if tipo_repeticao == 'semanal' and 'dia_semana' in lancamento_data:
                    dia_semana = lancamento_data.get('dia_semana')
                    if dia_semana is not None:
                        dia_semana = int(dia_semana)
                        if not (0 <= dia_semana <= 6):
                            return jsonify({
                                'success': False,
                                'error': f'Dia da semana deve estar entre 0 (domingo) e 6 (sábado) no lançamento {idx}'
                            }), 400
                        lancamento.dia_semana = dia_semana
                
                print("Adicionando lançamento à sessão...")
                db.session.add(lancamento)
                
                print("Calculando datas de ocorrência...")
                datas = lancamento.gerar_datas_lancamento(orcamento.data_inicio, orcamento.data_fim)
                print(f"Número de ocorrências geradas: {len(datas)}")
                
                if len(datas) > 100:  # Validação de segurança
                    print(f"Aviso: Número alto de ocorrências ({len(datas)})")
                    return jsonify({
                        'success': False,
                        'error': f'Número muito alto de ocorrências para o lançamento {idx} ({len(datas)}). Por favor, revise os parâmetros.'
                    }), 400

                valor_lancamento = float(valor) * len(datas)
                if valor_lancamento > 1000000:  # Validação de valor total
                    print(f"Aviso: Valor total muito alto ({valor_lancamento})")
                    return jsonify({
                        'success': False,
                        'error': f'Valor total muito alto para o lançamento {idx} (R$ {valor_lancamento:.2f}). Por favor, revise os valores.'
                    }), 400
                
                valor_total += valor_lancamento
                print(f"Valor calculado para o lançamento: {valor_lancamento}")
                
            except ValueError as e:
                print(f"Erro de validação no lançamento {idx}: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': f'Erro nos dados do lançamento {idx}: {str(e)}'
                }), 400
            except KeyError as e:
                print(f"Campo obrigatório ausente no lançamento {idx}: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': f'Campo obrigatório ausente no lançamento {idx}: {str(e)}'
                }), 400
            except Exception as e:
                print(f"Erro inesperado no lançamento {idx}: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': f'Erro inesperado no lançamento {idx}: {str(e)}'
                }), 400
        
        print(f"\nValor total calculado: {valor_total}")
        orcamento.valor_total = valor_total
        
        if not orcamento_id:
            print("Adicionando novo orçamento à sessão...")
            db.session.add(orcamento)
        
        print("Executando flush...")
        db.session.flush()
        
        print("Gerando previsões...")
        orcamento.gerar_previsoes()
        
        print("Executando commit...")
        db.session.commit()
        
        print("=== PROCESSO FINALIZADO COM SUCESSO ===")
        return jsonify({'success': True})
        
    except Exception as e:
        db.session.rollback()
        print("\n=== ERRO NO PROCESSAMENTO ===")
        print(f"Tipo do erro: {type(e).__name__}")
        print(f"Mensagem de erro: {str(e)}")
        import traceback
        print("Traceback completo:")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f"{type(e).__name__}: {str(e)}"
        }), 500

@orcamento_bp.route('/<int:id>/excluir', methods=['POST'])
@login_required
def excluir(id):
    """Exclui (soft delete) um orçamento."""
    try:
        orcamento = Orcamento.query.get_or_404(id)
        orcamento.deleted_at = datetime.now()
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@orcamento_bp.route('/<int:id>/historico')
@login_required
def historico(id):
    """Retorna o histórico de um orçamento específico."""
    historico = OrcamentoHistorico.query.filter_by(orcamento_id=id).order_by(
        OrcamentoHistorico.mes_referencia
    ).all()
    
    return jsonify([{
        'periodo': h.mes_referencia.strftime('%m/%Y'),
        'valor_orcado': float(h.valor_orcado),
        'valor_realizado': float(h.valor_realizado)
    } for h in historico])

@orcamento_bp.route('/relatorio/mensal')
@login_required
def relatorio_mensal():
    """Gera relatório mensal de orçamentos."""
    mes_atual = date.today().replace(day=1)
    
    # Busca todos os orçamentos ativos no mês atual
    orcamentos = db.session.query(
        Categoria.nome,
        Orcamento.valor_total,  # Corrigido
        func.coalesce(func.sum(Transacao.valor), 0).label('realizado')
    ).join(
        Categoria, Orcamento.categoria_id == Categoria.id
    ).outerjoin(
        Transacao,
        db.and_(
            Transacao.categoria_id == Orcamento.categoria_id,
            func.date_trunc('month', Transacao.data) == mes_atual,
            Transacao.deleted_at == None
        )
    ).filter(
        Orcamento.data_inicio <= mes_atual,
        Orcamento.data_fim >= mes_atual,
        Orcamento.deleted_at == None
    ).group_by(
        Categoria.nome,
        Orcamento.valor
    ).all()
    
    return jsonify([{
        'categoria': nome,
        'orcado': float(valor),
        'realizado': float(realizado),
        'percentual': round((realizado / valor * 100), 1) if valor > 0 else 0
    } for nome, valor, realizado in orcamentos])

@orcamento_bp.route('/alertas')
@login_required
def alertas():
    """Retorna alertas de orçamentos próximos ao limite."""
    hoje = date.today()
    
    alertas = db.session.query(
        Categoria.nome,
        Orcamento.valor_total,  # Atualizado de valor para valor_total
        func.sum(Transacao.valor).label('realizado')
    ).join(
        Categoria, Orcamento.categoria_id == Categoria.id
    ).join(
        Transacao,
        db.and_(
            Transacao.categoria_id == Orcamento.categoria_id,
            Transacao.data.between(Orcamento.data_inicio, Orcamento.data_fim),
            Transacao.deleted_at == None
        )
    ).filter(
        Orcamento.data_inicio <= hoje,
        Orcamento.data_fim >= hoje,
        Orcamento.deleted_at == None
    ).group_by(
        Categoria.nome,
        Orcamento.valor
    ).having(
        func.sum(Transacao.valor) >= Orcamento.valor * 0.75
    ).all()
    
    return jsonify([{
        'categoria': nome,
        'orcado': float(valor),
        'realizado': float(realizado),
        'percentual': round((realizado / valor * 100), 1)
    } for nome, valor, realizado in alertas])

@orcamento_bp.route('/previsao')
@login_required
def previsao():
    """Página de previsão orçamentária"""
    categorias = Categoria.query.filter_by(deleted_at=None).all()
    return render_template('orcamento/previsao.html', categorias=categorias)

@orcamento_bp.route('/api/previsao')
@login_required
def api_previsao():
    """API que retorna dados de previsão"""
    data_inicio = request.args.get('data_inicio', date.today().strftime('%Y-%m-%d'))
    data_fim = request.args.get('data_fim', '')
    
    if not data_fim:
        # Se não especificado, usa 3 meses à frente
        data_fim = (datetime.strptime(data_inicio, '%Y-%m-%d') + relativedelta(months=3)).strftime('%Y-%m-%d')
    
    # Busca transações efetivas
    transacoes = db.session.query(
        Transacao.data,
        db.func.sum(
            db.case(
                (Transacao.tipo.in_(['Receita', 'Receita Prevista']), Transacao.valor),
                else_=-Transacao.valor
            )
        ).label('valor_liquido')
    ).filter(
        Transacao.data.between(data_inicio, data_fim),
        Transacao.deleted_at == None,
        Transacao.ignored == False
    ).group_by(Transacao.data).all()
    
    # Busca previsões de orçamentos
    previsoes = db.session.query(
        OrcamentoPrevisao.data_prevista,
        db.func.sum(
            db.case(
                (OrcamentoPrevisao.realizado == False, -OrcamentoPrevisao.valor),
                else_=0
            )
        ).label('valor_previsto')
    ).join(
        Orcamento
    ).filter(
        OrcamentoPrevisao.data_prevista.between(data_inicio, data_fim),
        Orcamento.deleted_at == None
    ).group_by(OrcamentoPrevisao.data_prevista).all()
    
    # Calcula saldo inicial
    saldo_inicial = db.session.query(
        db.func.sum(Conta.saldo_inicial)
    ).filter_by(deleted_at=None).scalar() or 0
    
    # Monta a linha do tempo
    timeline = {}
    saldo_acumulado = float(saldo_inicial)
    
    # Adiciona transações efetivas
    for transacao in transacoes:
        data_str = transacao.data.strftime('%Y-%m-%d')
        if data_str not in timeline:
            timeline[data_str] = {'real': 0, 'previsto': 0}
        timeline[data_str]['real'] = float(transacao.valor_liquido)
    
    # Adiciona previsões
    for previsao in previsoes:
        data_str = previsao.data_prevista.strftime('%Y-%m-%d')
        if data_str not in timeline:
            timeline[data_str] = {'real': 0, 'previsto': 0}
        timeline[data_str]['previsto'] = float(previsao.valor_previsto)
    
    # Calcula saldos acumulados
    resultado = []
    for data_str in sorted(timeline.keys()):
        movimentos = timeline[data_str]
        saldo_acumulado += movimentos['real'] + movimentos['previsto']
        resultado.append({
            'data': data_str,
            'saldo_real': saldo_acumulado - movimentos['previsto'],
            'saldo_previsto': saldo_acumulado,
            'valor_real': movimentos['real'],
            'valor_previsto': movimentos['previsto']
        })
    
    return jsonify({
        'saldo_inicial': float(saldo_inicial),
        'timeline': resultado
    })

@orcamento_bp.route('/tipos_repeticao', methods=['GET'])
@login_required
def tipos_repeticao():
    """Retorna os tipos de repetição disponíveis."""
    return jsonify({
        'tipos': TipoRepeticao.choices()
    })