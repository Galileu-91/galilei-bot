import time
import random
import discord
from discord.ext import commands
from discord.ui import Button, View
import re
import os
import asyncio
import sys
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
from types import ModuleType

# --- BLINDAGEM CONTRA ERRO DE ÁUDIO ---
if 'audioop' not in sys.modules:
    mock_audioop = ModuleType('audioop')
    sys.modules['audioop'] = mock_audioop
    print("✅ Sistema de compatibilidade ativado")

# --- CONFIGURAÇÃO WEB (KEEP ALIVE) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot Galilei está Online!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- CONFIGURAÇÕES DO BOT ---
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix='!', intents=intents)

sessoes_usuarios = {}

# --- INTERFACE DAS QUESTÕES ---
class QuestaoView(View):
    def __init__(self, user_id, index, acertos, thread):
        super().__init__(timeout=360) 
        self.user_id = user_id
        self.index = index
        self.acertos = acertos
        self.thread = thread
        self.respondido = False
        self.message = None

        for letra in ["A", "B", "C", "D"]:
            btn = Button(label=letra, style=discord.ButtonStyle.blurple, custom_id=letra)
            btn.callback = self.processar_clique
            self.add_item(btn)

        btn_reset = Button(label="Sair/Reset", style=discord.ButtonStyle.secondary, emoji="🔄")
        btn_reset.callback = self.resetar_simulado
        self.add_item(btn_reset)

    async def resetar_simulado(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Não é sua sala!", ephemeral=True)
        await interaction.response.send_message("Limpando sala...", ephemeral=True)
        await self.thread.delete()

    async def processar_clique(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("❌ Use sua própria sala!", ephemeral=True)

        self.respondido = True
        escolha_letra = interaction.data['custom_id'].upper()
        questoes = sessoes_usuarios[self.user_id]
        q_atual = questoes[self.index]

        # ✅ Busca o texto da opção que o usuário clicou
        mapeamento = self.message.content.split('\n')
        texto_escolhido = ""
        for linha in mapeamento:
            if linha.lower().startswith(f"{escolha_letra.lower()}."):
                texto_escolhido = re.sub(r'^[a-d][\s\.)]+', '', linha).strip()

        if texto_escolhido.lower() == q_atual["texto_correto"].lower():
            self.acertos += 1
            feedback = "✅ **Correto!**"
        else:
            feedback = f"❌ **Errado!** A resposta era: **{q_atual['texto_correto']}**"

        proximo = self.index + 1
        if proximo < len(questoes):
            q_prox = questoes[proximo]
            alts_texto = list(q_prox["alternativas"])
            random.shuffle(alts_texto)
            
            novas_opcoes = [f"{l}. {t}" for l, t in zip(["a", "b", "c", "d"], alts_texto)]
            corpo_questao = f"**{q_prox['pergunta']}**\n\n" + "\n".join(novas_opcoes)

            nova_view = QuestaoView(self.user_id, proximo, self.acertos, self.thread)
            msg = await self.thread.send(
                content=f"{feedback}\n\n---\nQuestão {proximo + 1}:\n{corpo_questao}", 
                view=nova_view
            )
            nova_view.message = msg
            await interaction.response.edit_message(view=None)
        else:
            view_final = View()
            btn_sair = Button(label="Apagar Sala", style=discord.ButtonStyle.danger, emoji="🧹")
            btn_sair.callback = lambda it: asyncio.create_task(self.thread.delete())
            view_final.add_item(btn_sair)

            await self.thread.send(
                content=f"{feedback}\n\n🏆 **Simulado Concluído!**\nAcertos: **{self.acertos}/{len(questoes)}**", 
                view=view_final
            )
            await interaction.response.edit_message(view=None)

# --- MENU PRINCIPAL (CORRIGIDO) ---
class MenuSimulado(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Probabilidade e Estatística", style=discord.ButtonStyle.secondary, row=1)
    async def btn_plan(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.preparar_sala(interaction, "Probabilidade e Estatística.txt")

    @discord.ui.button(label="Fundamentos de Sistemas de Informação", style=discord.ButtonStyle.secondary, row=1)
    async def btn_seg(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.preparar_sala(interaction, "Fundamentos de Sistemas de Informação.txt")

    @discord.ui.button(label="Fundamentos de Gestão Empresarial", style=discord.ButtonStyle.secondary, row=2)
    async def btn_sad(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.preparar_sala(interaction, "Fundamentos de Gestão Empresarial.txt")

    async def preparar_sala(self, interaction, nome_arquivo):
        thread = await interaction.channel.create_thread(
            name=f"Estudo-{interaction.user.name}",
            type=discord.ChannelType.public_thread 
        )
        await interaction.response.send_message(f"✅ Sala criada: {thread.mention}", ephemeral=True)
        await self.iniciar_logica(interaction, nome_arquivo, thread)

    # ✅ AGORA ESTÁ DENTRO DA CLASSE (Indentação correta)
    async def iniciar_logica(self, interaction, nome_arquivo, thread):
        caminho = os.path.join("Simulados", nome_arquivo)
        if not os.path.exists(caminho):
            return await thread.send(f"❌ Arquivo `{nome_arquivo}` não encontrado.")

        with open(caminho, 'r', encoding='utf-8') as f:
            conteudo = f.read()

        # ✅ Split aprimorado para o seu formato "#. "
        blocos = [b.strip() for b in re.split(r'#\.?|#', conteudo) if b.strip()]
        questoes_lista = []
        
        for bloco in blocos:
            res = re.search(r'resposta correta é:\s*([a-d])', bloco, re.IGNORECASE)
            letra_original = res.group(1).lower() if res else "a"

            linhas = bloco.split('\n')
            enunciado_acumulado = []
            alternativas_limpas = []
            texto_correto = ""
            
            for linha in linhas:
                l_s = linha.strip()
                if not l_s or "escolha uma opção" in l_s.lower(): continue

                if re.match(r'^[a-d][\s\.)]', l_s, re.IGNORECASE) and "resposta correta é" not in l_s.lower():
                    txt = re.sub(r'^[a-d][\s\.)]+', '', l_s).strip()
                    alternativas_limpas.append(txt)
                    if l_s.lower().startswith(letra_original):
                        texto_correto = txt
                elif "resposta correta é" in l_s.lower():
                    continue
                else:
                    enunciado_acumulado.append(l_s)

            if alternativas_limpas and texto_correto:
                questoes_lista.append({
                    "pergunta": "\n".join(enunciado_acumulado),
                    "alternativas": alternativas_limpas,
                    "texto_correto": texto_correto
                })

        if not questoes_lista:
            return await thread.send("⚠️ Erro ao ler questões!")

        random.shuffle(questoes_lista)
        sessoes_usuarios[interaction.user.id] = questoes_lista

        q = questoes_lista[0]
        alts = list(q["alternativas"])
        random.shuffle(alts)
        
        opcoes = [f"{l}. {t}" for l, t in zip(["a", "b", "c", "d"], alts)]
        corpo = f"**{q['pergunta']}**\n\n" + "\n".join(opcoes)

        view = QuestaoView(interaction.user.id, 0, 0, thread)
        msg = await thread.send(content=f"Questão 1:\n{corpo}", view=view)
        view.message = msg

# --- COMANDOS ---
@bot.command()
async def menu(ctx):
    embed = discord.Embed(title="📚 Central de Simulados", color=discord.Color.blue())
    await ctx.send(embed=embed, view=MenuSimulado())

@bot.command(name="limpar")
@commands.has_permissions(manage_messages=True)
async def limpar(ctx, quantidade: int = 100):
    await ctx.message.delete()
    await ctx.channel.purge(limit=min(quantidade, 100))

@bot.event
async def on_ready():
    print(f"✅ Galilei Online")

if __name__ == "__main__":
    if TOKEN:
        keep_alive()
        bot.run(TOKEN)