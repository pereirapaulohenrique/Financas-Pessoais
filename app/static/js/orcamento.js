document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM carregado, inicializando handlers de orçamento...');
    
    // Configura lançamentos existentes
    document.querySelectorAll('.lancamento-item').forEach(item => {
        configurarRecorrencia(item);
    });
});

let lancamentoCounter = 0;

function adicionarLancamento(dados = null) {
    console.log('Adicionando novo lançamento:', dados);
    
    const template = document.getElementById('lancamentoTemplate');
    const container = document.getElementById('lancamentosContainer');
    
    if (!template || !container) {
        console.error('Template ou container não encontrado');
        return;
    }
    
    const clone = template.content.cloneNode(true);
    const lancamentoId = `lancamento-${Date.now()}`;
    
    // Substitui o placeholder {ID} nos elementos
    clone.innerHTML = clone.innerHTML.replace(/{ID}/g, lancamentoId);
    
    // Adiciona o clone ao container
    container.appendChild(clone);
    
    // Configura os listeners para os campos de recorrência
    const lancamentoElement = container.lastElementChild;
    configurarRecorrencia(lancamentoElement);
    
    if (dados) {
        preencherDadosLancamento(lancamentoElement, dados);
    }
}

function configurarRecorrencia(lancamentoElement) {
    console.log('Configurando recorrência para elemento:', lancamentoElement);
    
    // Garantir que estamos pegando os elementos dentro do lançamento específico
    const selectPeriodo = lancamentoElement.querySelector('select.lancamento-periodo');
    const divDiasSemana = lancamentoElement.querySelector('div.lancamento-dias-semana');
    const divRepeticaoMensal = lancamentoElement.querySelector('div.lancamento-repeticao-mensal');
    
    console.log('Elementos encontrados:', {
        selectPeriodo: selectPeriodo ? 'sim' : 'não',
        divDiasSemana: divDiasSemana ? 'sim' : 'não',
        divRepeticaoMensal: divRepeticaoMensal ? 'sim' : 'não'
    });

    if (!selectPeriodo || !divDiasSemana || !divRepeticaoMensal) {
        console.error('Elementos necessários não encontrados');
        return;
    }

    // Remover event listeners anteriores (se existirem)
    selectPeriodo.removeEventListener('change', handlePeriodoChange);
    
    // Função de handler de mudança
    function handlePeriodoChange() {
        console.log('Período mudou para:', this.value);
        
        // Esconde todas as opções extras primeiro
        divDiasSemana.style.display = 'none';
        divRepeticaoMensal.style.display = 'none';
        
        // Mostra as opções relevantes baseado na seleção
        switch(this.value) {
            case 'week':
                console.log('Mostrando opções semanais');
                divDiasSemana.style.display = 'block';
                break;
            case 'month':
                console.log('Mostrando opções mensais');
                divRepeticaoMensal.style.display = 'block';
                break;
        }
    }
    
    // Adiciona o novo event listener
    selectPeriodo.addEventListener('change', handlePeriodoChange);
    
    // Dispara o evento de mudança para configurar o estado inicial
    selectPeriodo.dispatchEvent(new Event('change'));
}

function adicionarLancamento(dados = null) {
    console.log('Adicionando novo lançamento:', dados);
    
    const template = document.getElementById('lancamentoTemplate');
    const container = document.getElementById('lancamentosContainer');
    
    if (!template || !container) {
        console.error('Template ou container não encontrado');
        return;
    }
    
    const clone = template.content.cloneNode(true);
    const lancamentoId = `lancamento-${Date.now()}`;
    
    // Substitui o placeholder {ID} nos elementos
    const cloneHtml = clone.innerHTML.replace(/{ID}/g, lancamentoId);
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = cloneHtml;
    
    // Adiciona o elemento ao container
    const newElement = container.appendChild(tempDiv.firstElementChild);
    
    // Configura os listeners para os campos de recorrência
    configurarRecorrencia(newElement);
    
    if (dados) {
        preencherDadosLancamento(newElement, dados);
    }
    
    return newElement;
}

function preencherDadosLancamento(element, dados) {
    console.log('Preenchendo dados do lançamento:', dados);
    
    if (dados.data_inicial) {
        element.querySelector('.lancamento-data-inicial').value = dados.data_inicial;
    }
    
    if (dados.valor) {
        element.querySelector('.lancamento-valor').value = dados.valor;
    }
    
    if (dados.descricao) {
        element.querySelector('.lancamento-descricao').value = dados.descricao;
    }
    
    const selectPeriodo = element.querySelector('.lancamento-periodo');
    if (selectPeriodo) {
        selectPeriodo.value = dados.tipo_repeticao || 'day';
        selectPeriodo.dispatchEvent(new Event('change'));
    }
    
    if (dados.dias_semana && Array.isArray(dados.dias_semana)) {
        dados.dias_semana.forEach(dia => {
            const checkbox = element.querySelector(`input[type="checkbox"][value="${dia}"]`);
            if (checkbox) checkbox.checked = true;
        });
    }
}

function removerLancamento(button) {
    console.log('Removendo lançamento');
    const lancamentoItem = button.closest('.lancamento-item');
    if (lancamentoItem) {
        lancamentoItem.remove();
    }
}

async function salvarOrcamento() {
    try {
        const form = document.getElementById('formOrcamento');
        const formData = new FormData(form);

        // Coleta os dados dos lançamentos
        const lancamentos = [];
        document.querySelectorAll('.lancamento-item').forEach(item => {
            const lancamento = {
                data_inicial: item.querySelector('.lancamento-data-inicial').value,
                valor: parseFloat(item.querySelector('.lancamento-valor').value),
                descricao: item.querySelector('.lancamento-descricao').value || '',
                intervalo: parseInt(item.querySelector('.lancamento-intervalo').value) || 1,
                periodo: item.querySelector('.lancamento-periodo').value
            };

            // Adiciona dados específicos baseado no tipo de recorrência
            switch(lancamento.periodo) {
                case 'week':
                    lancamento.dias_semana = Array.from(
                        item.querySelectorAll('input[type="checkbox"]:checked')
                    ).map(cb => parseInt(cb.value));
                    break;
                case 'month':
                    lancamento.tipo_repeticao_mensal = item.querySelector('input[name^="tipo-mes-"]:checked').value;
                    break;
            }

            lancamentos.push(lancamento);
        });

        formData.append('lancamentos', JSON.stringify(lancamentos));

        const response = await fetch('/orcamento/salvar', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const contentType = response.headers.get("content-type");
            if (contentType && contentType.indexOf("application/json") !== -1) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Erro ao salvar orçamento');
            } else {
                const text = await response.text();
                throw new Error('Erro no servidor. Por favor, tente novamente.');
            }
        }

        const data = await response.json();
        
        if (data.success) {
            alert('Orçamento salvo com sucesso!');
            window.location.href = '/orcamento/';
        } else {
            throw new Error(data.error || 'Erro ao salvar orçamento');
        }

    } catch (error) {
        console.error('Erro ao salvar:', error);
        alert('Erro ao salvar orçamento: ' + error.message);
    }
}