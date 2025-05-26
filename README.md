# EC2 Instance Cloner

Este script permite clonar uma instância EC2 existente com uma nova AMI, preservando todas as outras configurações, incluindo grupos de segurança, perfis IAM, tags, opções de metadados e volumes EBS.

## Funcionalidades

- Clona uma instância EC2 existente usando uma nova AMI
- **Busca automaticamente as AMIs mais recentes** criadas pelo AWS Backup para a instância
- **Coloca automaticamente a nova instância em uma AZ diferente da original** (para melhor resiliência)
- **Preserva o tipo de volume raiz** da instância original, evitando erros de compatibilidade
- Preserva todas as configurações da instância original:
  - Tipo de instância
  - Sub-rede (com adaptação inteligente para diferentes AZs)
  - Grupos de segurança
  - Key pair
  - User data
  - Perfil IAM
  - Configurações de IMDS (IMDSv2)
  - Monitoramento detalhado
  - EBS Optimized
  - Tenancy
  - Configurações de crédito para instâncias T
  - Opções de hibernação
  - Opções de enclave
  - Volumes EBS adicionais
  - Tags
- Permite especificar um novo nome para a instância clonada
- Formata automaticamente o nome com sufixo "-DR-DD/MM/AAAA"
- Adiciona tags de rastreamento para identificar a instância de origem
- Interface amigável com emojis e informações detalhadas durante o processo
- **Gera relatório detalhado** ao final da execução com informações completas sobre a clonagem

## Pré-requisitos

- Python 3.6+
- Biblioteca boto3 (`pip install boto3`)
- Credenciais AWS configuradas (~/.aws/credentials ou variáveis de ambiente)
- Permissões IAM apropriadas para descrever e criar instâncias EC2

## Instalação

```bash
# Clonar o repositório (ou criar manualmente a estrutura de diretórios)
mkdir -p ~/projects/python/CloneInstance/libs

# Instalar dependências
pip install boto3
```

## Uso

```bash
# Uso básico - busca automática de AMIs
./clone_ec2.py --instance-id i-0123456789abcdef0 --profile dev

# Especificando uma AMI específica
./clone_ec2.py --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --profile dev

# Com nome personalizado
./clone_ec2.py --instance-id i-0123456789abcdef0 --new-name WebServer --profile dev

# Especificando a região
./clone_ec2.py --instance-id i-0123456789abcdef0 --region us-east-1 --profile dev
```

### Parâmetros

- `--instance-id`: ID da instância a ser clonada (obrigatório)
- `--profile`: Nome do perfil AWS a ser usado (obrigatório, ex: dev, hml, prd)
- `--new-ami-id`: ID da nova AMI a ser usada (opcional). Se não for fornecido, o script buscará automaticamente as AMIs mais recentes da instância
- `--new-name`: Novo nome para a instância (opcional). Será formatado como `<novo-nome>-DR-DD/MM/AAAA`
- `--region`: Região AWS onde a instância está localizada (padrão: us-east-1)

## Exemplos

### Exemplo 1: Busca automática de AMIs

```bash
./clone_ec2.py --instance-id i-0123456789abcdef0 --profile dev
```

Este comando buscará automaticamente as AMIs mais recentes criadas para a instância `i-0123456789abcdef0` e permitirá que você escolha qual usar. O nome da nova instância será o mesmo da instância original com o sufixo `-DR-DD/MM/AAAA`.

### Exemplo 2: Clonagem com AMI específica e novo nome

```bash
./clone_ec2.py --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --new-name WebServer --profile dev
```

Este comando clonará a instância `i-0123456789abcdef0` usando a AMI `ami-0abcdef1234567890`. O nome da nova instância será `WebServer-DR-DD/MM/AAAA`.

## Compatibilidade de Volumes

O script verifica automaticamente se o tipo de volume raiz da instância original (ex: gp2, gp3) é diferente do tipo proposto pela AMI. Se forem diferentes, o script preserva o tipo de volume da instância original, evitando erros como:

```
InvalidParameterCombination: The parameter iops is not supported for gp2 volumes
```

Isso é especialmente útil quando:
- A AMI foi criada quando a instância usava um tipo de volume (ex: gp2)
- A instância foi posteriormente atualizada para outro tipo (ex: gp3)
- Ao clonar, o script mantém o tipo atual da instância (gp3), não o da AMI (gp2)

## Alta Disponibilidade

Para melhorar a resiliência, o script sempre tenta colocar a nova instância em uma Zona de Disponibilidade (AZ) diferente da instância original:

- A nova instância será colocada em uma AZ diferente automaticamente
- Isso ajuda a proteger contra falhas de AZ, seguindo as melhores práticas de alta disponibilidade
- As sub-redes são selecionadas de acordo com a nova AZ

## Estrutura do Projeto

```
~/projects/python/CloneInstance/
├── clone_ec2.py           # Script principal executável
├── README.md              # Este arquivo
└── libs/
    ├── __init__.py        # Torna o diretório um pacote Python
    ├── ec2_clone_functions.py  # Funções principais para clonagem
    ├── ec2_volume_utils.py     # Funções para manipulação de volumes
    └── ami_finder.py           # Funções para busca de AMIs
```

## Solução de Problemas

### Erro: "No module named 'boto3'"

Instale a biblioteca boto3:

```bash
pip install boto3
```

### Erro: "Could not connect to the endpoint URL"

Verifique se a região AWS está correta e se você tem conectividade com a AWS.

### Erro: "An error occurred (UnauthorizedOperation)"

Verifique se suas credenciais AWS têm permissões suficientes para descrever e criar instâncias EC2.

### Erro: "No AMI found for instance"

O script não conseguiu encontrar AMIs criadas pelo AWS Backup para a instância especificada. Verifique se:
1. A instância tem backups configurados
2. O AWS Backup está criando AMIs para a instância
3. As AMIs têm o ID da instância na descrição ou nome

### Erro: "InvalidParameterCombination"

Se você ainda encontrar erros relacionados a combinações inválidas de parâmetros para volumes, verifique se a instância tem configurações de volume especiais que podem não ser compatíveis com a AMI.

## Relatório Final

Ao concluir a clonagem, o script gera automaticamente um relatório detalhado com informações importantes:

```
===Consigcard===

Account: DEV

Aplicação: 

EC2: WebServer-DR-25/05/2025 - i-0z9y8x7w6v5u4t3s
AMI: ami-0123456789abcdef0
(A original era i-0a1b2c3d4e5f6g7h8)
AZ: us-east-1b (original era us-east-1a)
Sub: subnet-def456abc789 (original era subnet-abc123def456)

Removida do LB: 
Voltou ao LB: 
Inicio: 20:15
Fim: 20:23

Novo IP: 10.0.2.45 (original era 10.0.1.123)
```

O relatório é exibido no terminal e também salvo em um arquivo de texto para referência futura. Ele inclui:

- Informações da instância original e da nova instância
- Detalhes sobre a AMI utilizada
- Zonas de disponibilidade e subnets
- Horários precisos de início e fim do processo
- Endereços IP das instâncias

Alguns campos são deixados em branco para preenchimento manual, como "Aplicação", "Removida do LB" e "Voltou ao LB".
