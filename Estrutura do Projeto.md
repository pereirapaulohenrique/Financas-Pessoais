```
financeapp/
│
├── .env                     # Variáveis de ambiente
├── requirements.txt         # Dependências do projeto
├── config.py               # Configurações do projeto
├── run.py                  # Ponto de entrada da aplicação
│
├── app/
│   ├── __init__.py         # Inicialização da aplicação
│   │
│   ├── models/             # Modelos do banco de dados
│   │   ├── __init__.py
│   │   ├── base.py        # Modelo base com campos comuns
│   │   ├── usuario.py
│   │   ├── conta.py
│   │   ├── categoria.py
│   │   ├── transacao.py
│   │   └── cartao.py
│   │
│   ├── services/          # Lógica de negócio
│   │   ├── __init__.py
│   │   ├── auth.py       # Serviço de autenticação
│   │   ├── usuario.py
│   │   ├── conta.py
│   │   ├── categoria.py
│   │   ├── transacao.py
│   │   └── cartao.py
│   │
│   ├── routes/           # Rotas da aplicação
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── usuario.py
│   │   ├── conta.py
│   │   ├── categoria.py
│   │   ├── transacao.py
│   │   └── dashboard.py
│   │
│   ├── static/          # Arquivos estáticos
│   │   ├── css/
│   │   ├── js/
│   │   └── img/
│   │
│   ├── templates/       # Templates HTML
│   │   ├── base.html   # Template base
│   │   ├── auth/
│   │   ├── dashboard/
│   │   ├── conta/
│   │   ├── categoria/
│   │   └── transacao/
│   │
│   └── utils/          # Utilitários
│       ├── __init__.py
│       ├── decorators.py
│       ├── validators.py
│       └── helpers.py
│
├── migrations/         # Migrações do banco de dados
│
└── tests/             # Testes
    ├── __init__.py
    ├── test_models.py
    ├── test_routes.py
    └── test_services.py
```