# 🌐 Monitor de Rede & Latência (v25)

Aplicação interativa em Python utilizando **Streamlit** para monitoramento em tempo real de conexões de rede, disponibilidade de serviços web e telemetria de hardware via SSH.

> ℹ️ **Nota de Compatibilidade:** A telemetria de hardware (Aba 3) foi desenvolvida e testada especificamente para o **Modem Wi-Fi 6 da Operadora VIVO** (Modelo **MitraStar GPT-2742GX4X5**).

---

## 🚀 Funcionalidades

* **⚡ Latência Externa & DNS Públicos:** Monitoramento contínuo de latência (ms) e perda de pacotes (%) em servidores DNS e Gateway local, com histórico dos últimos 30 minutos.
* **🌐 Status de Serviços Web:** Checagem de disponibilidade HTTP/HTTPS em tempo real de redes sociais, plataformas de streaming, bancos e jogos.
* **📡 Métricas ONT/Roteador (SSH):** Coleta automática via SSH do *Uptime*, consumo de memória RAM e uso de CPU adaptada para a ONT **MitraStar GPT-2742GX4X5 (Vivo Wi-Fi 6)**, utilizando cache de 120s para prevenir picos no processamento do roteador.

---

## 🛠️ Pré-requisitos

* **Python 3.8+**
* Conexão com a rede local da ONT.
* Acesso SSH liberado e credenciais do **Modem Wi-Fi 6 Vivo (MitraStar GPT-2742GX4X5)**.

---

## ⚙️ Passo a Passo de Configuração 

### 1. Criar o arquivo `.gitignore`
Crie um arquivo chamado `.gitignore` na raiz do projeto para proteger suas informações pessoais antes de enviar ao GitHub:

```text
.env
__pycache__/
*.pyc
venv/
.venv/
```
---

## 🏃‍♂️ Como Executar

Você pode executar a aplicação de duas formas no Windows:

### Opção 1: Via arquivo executável (.bat)
Dê um duplo clique no arquivo `executar.bat` (ou o nome que deu ao seu arquivo `.bat`) na raiz do projeto.

### Opção 2: Via Terminal
Execute o comando do Streamlit:

```bash
streamlit run monitor_v25.py
```
---