import React, { useState } from 'react';
import Papa from 'papaparse';

const CSVImport = ({ onDataReady }) => {
  const [csvPreview, setCSVPreview] = useState(null);
  const [columnMapping, setColumnMapping] = useState({});
  const [step, setStep] = useState('upload'); // upload, mapping, or preview
  
  // Campos necessários para cada modo
  const requiredFields = {
    conta: [
      { key: 'data', label: 'Data' },
      { key: 'tipo', label: 'Tipo (Receita/Despesa)' },
      { key: 'conta', label: 'Conta' },
      { key: 'categoria', label: 'Categoria' },
      { key: 'descricao', label: 'Descrição' },
      { key: 'valor', label: 'Valor' },
      { key: 'lancamento_futuro', label: 'Lançamento Futuro' }
    ],
    cartao: [
      { key: 'data', label: 'Data' },
      { key: 'cartao', label: 'Cartão' },
      { key: 'categoria', label: 'Categoria' },
      { key: 'descricao', label: 'Descrição' },
      { key: 'valor', label: 'Valor' },
      { key: 'parcelas', label: 'Parcelas' }
    ]
  };

  const handleFileUpload = (event) => {
    const file = event.target.files[0];
    if (file) {
      Papa.parse(file, {
        preview: 5, // Mostrar apenas primeiras 5 linhas na prévia
        header: true,
        skipEmptyLines: true,
        complete: function(results) {
          setCSVPreview(results);
          setStep('mapping');
        }
      });
    }
  };

  const handleMapping = (fieldKey, csvColumn) => {
    setColumnMapping(prev => ({
      ...prev,
      [fieldKey]: csvColumn
    }));
  };

  const processData = () => {
    if (!csvPreview) return;
    
    // Mapear dados do CSV para o formato esperado
    const processedData = csvPreview.data.map(row => {
      const mappedRow = {};
      Object.entries(columnMapping).forEach(([field, csvColumn]) => {
        mappedRow[field] = row[csvColumn];
      });
      return mappedRow;
    });
    
    onDataReady(processedData);
  };

  return (
    <div className="space-y-4">
      {step === 'upload' && (
        <div className="p-4 border-2 border-dashed rounded-lg text-center">
          <input
            type="file"
            accept=".csv"
            onChange={handleFileUpload}
            className="hidden"
            id="csv-upload"
          />
          <label htmlFor="csv-upload" className="cursor-pointer">
            <div className="p-6">
              <i className="fas fa-upload text-3xl mb-2"></i>
              <p>Clique para selecionar ou arraste um arquivo CSV</p>
            </div>
          </label>
        </div>
      )}

      {step === 'mapping' && csvPreview && (
        <div>
          <h3 className="text-lg font-semibold mb-4">Mapeamento de Colunas</h3>
          <div className="grid gap-4">
            {requiredFields.conta.map(field => (
              <div key={field.key} className="flex items-center gap-4">
                <label className="w-40">{field.label}:</label>
                <select
                  className="form-select"
                  onChange={(e) => handleMapping(field.key, e.target.value)}
                  value={columnMapping[field.key] || ''}
                >
                  <option value="">Selecione a coluna</option>
                  {Object.keys(csvPreview.data[0] || {}).map(column => (
                    <option key={column} value={column}>{column}</option>
                  ))}
                </select>
              </div>
            ))}
          </div>

          <div className="mt-4">
            <h4 className="font-semibold mb-2">Prévia dos Dados:</h4>
            <div className="overflow-x-auto">
              <table className="table-auto w-full">
                <thead>
                  <tr>
                    {Object.keys(csvPreview.data[0] || {}).map(header => (
                      <th key={header} className="px-4 py-2">{header}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {csvPreview.data.slice(0, 5).map((row, i) => (
                    <tr key={i}>
                      {Object.values(row).map((cell, j) => (
                        <td key={j} className="border px-4 py-2">{cell}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="mt-4 flex justify-end gap-2">
            <button 
              className="btn btn-secondary"
              onClick={() => setStep('upload')}
            >
              Voltar
            </button>
            <button 
              className="btn btn-primary"
              onClick={processData}
            >
              Importar Dados
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default CSVImport;