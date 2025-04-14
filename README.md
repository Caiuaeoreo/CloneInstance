# EC2 Instance Cloner

Este script permite clonar uma instância EC2 existente com uma nova AMI, preservando todas as outras configurações, incluindo grupos de segurança, perfis IAM, tags, opções de metadados e volumes EBS. Também suporta clonagem entre regiões AWS diferentes.

## Funcionalidades

- Clona uma instância EC2 existente usando uma nova AMI
- Suporta clonagem entre regiões AWS diferentes
- **Coloca automaticamente a nova instância em uma AZ diferente da original** (para melhor resiliência)
- Preserva todas as configurações da instância original:
  - Tipo de instância
  - Sub-rede (com adaptação inteligente para clonagem entre regiões e AZs)
  - Grupos de segurança (com adaptação para clonagem entre regiões)
  - Key pair (quando disponível na região de destino)
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
- Formata automaticamente o nome com sufixo "-DR-MM/AAAA"
- Adiciona tags de rastreamento para identificar a instância de origem

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
# Uso básico (mesma região)
./clone_ec2.py --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890

# Com nome personalizado
./clone_ec2.py --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --new-name WebServer

# Especificando a região de origem
./clone_ec2.py --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --region us-east-1

# Clonagem entre regiões diferentes
./clone_ec2.py --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --region us-east-1 --target-region us-west-2
```

### Parâmetros

- `--instance-id`: ID da instância a ser clonada (obrigatório)
- `--new-ami-id`: ID da nova AMI a ser usada (obrigatório)
- `--new-name`: Novo nome para a instância (opcional). Será formatado como `<novo-nome>-DR-MM/AAAA`
- `--region`: Região AWS onde a instância de origem está localizada (padrão: us-east-1)
- `--target-region`: Região AWS onde a nova instância será criada (opcional). Se não especificado, usa a mesma região da origem.

## Exemplos

### Exemplo 1: Clonagem básica na mesma região

```bash
./clone_ec2.py --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890
```

Este comando clonará a instância `i-0123456789abcdef0` usando a AMI `ami-0abcdef1234567890` na mesma região. O nome da nova instância será o mesmo da instância original com o sufixo `-DR-MM/AAAA`.

### Exemplo 2: Clonagem com novo nome

```bash
./clone_ec2.py --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --new-name WebServer
```

Este comando clonará a instância `i-0123456789abcdef0` usando a AMI `ami-0abcdef1234567890`. O nome da nova instância será `WebServer-DR-MM/AAAA`.

### Exemplo 3: Clonagem entre regiões diferentes

```bash
./clone_ec2.py --instance-id i-0123456789abcdef0 --new-ami-id ami-0abcdef1234567890 --region us-east-1 --target-region us-west-2
```

Este comando clonará a instância `i-0123456789abcdef0` da região `us-east-1` para a região `us-west-2` usando a AMI `ami-0abcdef1234567890`. 

**Nota**: Para clonagem entre regiões, a AMI especificada deve existir na região de destino. O script fará adaptações inteligentes para sub-redes, grupos de segurança e key pairs.

## Considerações para clonagem entre regiões

Quando clonar entre regiões diferentes, o script:

1. **Sub-redes**: Tentará encontrar uma sub-rede na mesma letra de AZ (a, b, c) na região de destino
2. **Grupos de segurança**: Usará o grupo de segurança padrão na região de destino
3. **Key pair**: Verificará se o mesmo key pair existe na região de destino
4. **AMI**: Verificará se a AMI especificada existe na região de destino
5. **Tags adicionais**: Adicionará tags `SourceInstanceId` e `SourceRegion` para rastreabilidade

## Alta Disponibilidade

Para melhorar a resiliência, o script sempre tenta colocar a nova instância em uma Zona de Disponibilidade (AZ) diferente da instância original:

- Quando clonando na mesma região, a nova instância será colocada em uma AZ diferente automaticamente
- Isso ajuda a proteger contra falhas de AZ, seguindo as melhores práticas de alta disponibilidade
- As sub-redes são selecionadas de acordo com a nova AZ

## Estrutura do Projeto

```
~/projects/python/CloneInstance/
├── clone_ec2.py           # Script principal executável
├── README.md              # Este arquivo
└── libs/
    ├── __init__.py        # Torna o diretório um pacote Python
    └── ec2_clone_functions.py  # Funções para clonar instâncias EC2
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

### Erro: "AMI not found in target region"

Certifique-se de que a AMI especificada existe na região de destino. AMIs são específicas de cada região.
