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
    print("✅ Sistema de compatibilidade ativado (Sem erros de áudio)")

# --- CONFIGURAÇÃO WEB (KEEP ALIVE) ---
app = Flask('')
@app.route('/')
def home(): return "Bot Galilei está Online!"

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

        bot.loop.create_task(self.contagem_regressiva())

    async def contagem_regressiva(self):
        await asyncio.sleep(240) 
        if not self.respondido and self.message:
            try:
                for item in self.children:
                    if isinstance(item, Button) and item.label != "Sair/Reset":
                        item.disabled = True
                await self.message.edit(content=f"{self.message.content}\n\n⏰ **Tempo esgotado (240s)!**", view=self)
            except: pass

    async def on_timeout(self):
        try: await self.thread.delete()
        except: pass

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

        mapeamento = self.message.content.split('\n')
        texto_escolhido = ""
        for linha in mapeamento:
            if linha.startswith(f"{escolha_letra}."):
                texto_escolhido = linha.split(". ", 1)[1].strip()

        if texto_escolhido.lower() == q_atual["texto_correto"].lower():
            self.acertos += 1
            feedback = f"✅ **Correto!**"
        else:
            feedback = f"❌ **Errado!** A resposta era: **{q_atual['texto_correto']}**"

        await interaction.response.edit_message(view=None)

        proximo = self.index + 1
        if proximo < len(questoes):
            q_prox = questoes[proximo]
            alts_texto = q_prox["alternativas"].copy()
            random.shuffle(alts_texto)
            
            novas_opcoes = [f"{l}. {t}" for l, t in zip(["A", "B", "C", "D"], alts_texto)]
            corpo_questao = f"**{q_prox['pergunta']}**\n\n" + "\n".join(novas_opcoes)

            nova_view = QuestaoView(self.user_id, proximo, self.acertos, self.thread)
            msg = await self.thread.send(
                content=f"{feedback}\n\n---\nQuestão {proximo + 1}:\n{corpo_questao}", 
                view=nova_view
            )
            nova_view.message = msg
        else:
            view_final = View()
            btn_repetir = Button(label="Repetir Simulado", style=discord.ButtonStyle.success, emoji="🔄")
            
            async def repetir_callback(it: discord.Interaction):
                await it.response.defer(ephemeral=True) 
                async for msg in self.thread.history(limit=100):
                    await msg.delete()
                random.shuffle(sessoes_usuarios[self.user_id])
                nova_view = QuestaoView(self.user_id, 0, 0, self.thread)
                q_ini = sessoes_usuarios[self.user_id][0]
                alts = q_ini["alternativas"].copy()
                random.shuffle(alts)
                opcoes = [f"{l}. {t}" for l, t in zip(["A", "B", "C", "D"], alts)]
                msg = await self.thread.send(content=f"🎲 **Simulado Reiniciado!**\n\nQuestão 1:\n**{q_ini['pergunta']}**\n\n" + "\n".join(opcoes), view=nova_view)
                nova_view.message = msg

            btn_repetir.callback = repetir_callback
            btn_sair = Button(label="Apagar Sala", style=discord.ButtonStyle.danger, emoji="🧹")
            btn_sair.callback = lambda it: asyncio.create_task(self.thread.delete())
            
            view_final.add_item(btn_repetir)
            view_final.add_item(btn_sair)

            # ✅ CORREÇÃO DO ERRO DO VS CODE (self.acertos)
            await self.thread.send(
                content=f"{feedback}\n\n🏆 **Simulado Concluído!**\nAcertos: **{self.acertos}/{len(questoes)}**", 
                view=view_final
            )

# --- MENU PRINCIPAL (ESTILO ALFREDO) ---

class MenuSimulado(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Probabilidade e Estatística", style=discord.ButtonStyle.secondary, row=1)
    async def btn1(self, it, btn): await self.preparar_sala(it, "Probabilidade e Estatística.txt")

    @discord.ui.button(label="Fundamentos de Sistemas de Informação", style=discord.ButtonStyle.secondary, row=1)
    async def btn2(self, it, btn): await self.preparar_sala(it, "Fundamentos de Sistemas de Informação.txt")

    @discord.ui.button(label="Fundamentos de Gestão Empresarial", style=discord.ButtonStyle.secondary, row=2)
    async def btn3(self, it, btn): await self.preparar_sala(it, "Fundamentos de Gestão Empresarial.txt")

    async def preparar_sala(self, interaction, nome_arquivo):
        # 1. Cria a thread primeiro
        thread = await interaction.channel.create_thread(
            name=f"Estudo-{interaction.user.name}",
            type=discord.ChannelType.public_thread,
            auto_archive_duration=1440
        )
        
        # 2. Responde UMA ÚNICA VEZ (Isso evita a duplicação e o erro de interação)
        await interaction.response.send_message(f"✅ Sala criada, clique aqui 👉 {thread.mention}", ephemeral=True)
        
        # 3. Chama a lógica de carregar as questões
        await self.iniciar_logica(interaction, nome_arquivo, thread)

    async def iniciar_logica(self, interaction, nome_arquivo, thread):
        caminho = os.path.join("Simulados", nome_arquivo)
        if not os.path.exists(caminho):
            return await thread.send(f"❌ Arquivo `{nome_arquivo}` não encontrado no servidor.")

        # Aviso visual na thread
        msg_loading = await thread.send("📘 **Iniciando simulado...**")

        try:
            with open(caminho, "r", encoding="utf-8") as f:
                conteudo = f.read()
                # Divide pelos separadores que colocamos nos arquivos novos
                blocos = [b for b in conteudo.split("---") if b.strip()]

            questoes_lista = []
            for bloco in blocos:
                linhas = [l.strip() for l in bloco.strip().split('\n') if l.strip()]
                q_data = {"pergunta": "", "alternativas": [], "texto_correto": ""}
                alts_dict = {}

                for linha in linhas:
                    if linha.upper().startswith("QUESTAO:"):
                        q_data["pergunta"] = linha.split(":", 1)[1].strip()
                    elif linha.upper().startswith(("A:", "B:", "C:", "D:")):
                        letra = linha[0].upper()
                        texto = linha[2:].strip()
                        alts_dict[letra] = texto
                        q_data["alternativas"].append(texto)
                    elif linha.upper().startswith("GABARITO:"):
                        gab = linha.split(":", 1)[1].strip().upper()
                        if gab in alts_dict:
                            q_data["texto_correto"] = alts_dict[gab]

                if q_data["pergunta"] and q_data["texto_correto"]:
                    questoes_lista.append(q_data)

            if questoes_lista:
                random.shuffle(questoes_lista)
                sessoes_usuarios[interaction.user.id] = questoes_lista
                
                q = questoes_lista[0]
                alts_embaralhadas = q["alternativas"].copy()
                random.shuffle(alts_embaralhadas)
                
                opcoes_f = [f"{l}. {t}" for l, t in zip(["A", "B", "C", "D"], alts_embaralhadas)]
                corpo = f"**{q['pergunta']}**\n\n" + "\n".join(opcoes_f)

                view = QuestaoView(interaction.user.id, 0, 0, thread)
                await msg_loading.delete() # Apaga o "carregando"
                msg_final = await thread.send(content=f"Questão 1:\n{corpo}", view=view)
                view.message = msg_final
            else:
                await thread.send("⚠️ Erro: Não encontrei questões válidas dentro do arquivo.")

        except Exception as e:
            print(f"Erro na leitura: {e}")
            await thread.send(f"❌ Erro técnico ao ler o simulado.")

# --- COMANDOS (SEU CABEÇALHO COMPLETO) ---
@bot.command()
async def menu(ctx):
    embed = discord.Embed(
        title="📚 Central de Simulados (1/1)",
        description=(
            "Aqui estão as provas disponíveis neste servidor.\n"
            "Você pode iniciar um simulado clicando no botão correspondente abaixo.\n\n"
            "**Probabilidade e Estatística**\n"
            "📌 Vinculado por: @Galileu Meirelles\n\n"
            "**Fundamentos de Sistemas de Informação**\n"
            "📌 Vinculado por: @Galileu Meirelles\n\n"
            "**Fundamentos de Gestão Empresarial**\n"
            "📌 Vinculado por: @Galileu Meirelles\n\n"
            "🔹 *Clique em um dos botões abaixo para abrir sua sala privada!*"
        ),
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=MenuSimulado())

@bot.command(name="limpar")
@commands.has_permissions(manage_messages=True)
async def limpar(ctx, quantidade: int = 100):
    await ctx.message.delete()
    deleted = await ctx.channel.purge(limit=min(quantidade, 100))
    await ctx.send(f"🧹 {len(deleted)} mensagens limpas!", delete_after=3)

@bot.event
async def on_ready():
    print(f"✅ Galilei#0213 Online | Visual Alfredo | Sistema de Threads")

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)