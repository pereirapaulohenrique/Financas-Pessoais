import React from 'react';
import CSVImport from './CSVImport'; // Este é o componente que criamos anteriormente

const BulkImportPage = () => {
  const handleDataReady = (processedData) => {
    // Aqui vamos integrar com o Handsontable
    if (window.hot) {
      window.hot.loadData(processedData);
    }
  };

  return (
    <div className="w-full flex flex-col space-y-4">
      {/* Botões Toggle existentes */}
      <div className="flex justify-center gap-4">
        <button id="btn-conta" className="toggle-btn active">
          <i className="fas fa-wallet me-2"></i>Conta Corrente
        </button>
        <button id="btn-cartao" className="toggle-btn">
          <i className="fas fa-credit-card me-2"></i>Cartão de Crédito
        </button>
      </div>

      {/* Componente de importação CSV */}
      <CSVImport onDataReady={handleDataReady} />
      
      {/* Container para Handsontable */}
      <div id="hot-container" className="mt-4"></div>
    </div>
  );
};

export default BulkImportPage;