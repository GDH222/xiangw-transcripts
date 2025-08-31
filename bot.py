import discord
from discord.ext import commands
from discord import ui, ButtonStyle, SelectOption
import asyncio
import os
import re
import time
import math
import shutil
from typing import Optional, Dict, List
from pathlib import Path
from datetime import datetime

# Global variables
user_cooldowns = {}
COOLDOWN_SECONDS = 5

# CORRECT INTENTS SETUP
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="$", intents=intents)

class TicketForm(ui.Modal, title="Trade Information"):
    your_side = ui.TextInput(
        label="What is your side of the trade?",
        placeholder="What you're offering...",
        style=discord.TextStyle.long
    )
    their_side = ui.TextInput(
        label="What is their side of the trade?",
        placeholder="What they're offering...",
        style=discord.TextStyle.long
    )
    their_id = ui.TextInput(
        label="What is their user ID?",
        placeholder="Their Discord user ID..."
    )
    tip = ui.TextInput(
        label="What is the tip? (optional for trades below $50)",
        placeholder="Tip amount (optional)...",
        required=False
    )

    def __init__(self, ticket_type: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ticket_type = ticket_type
        if "trial" in ticket_type.lower() or "beginner" in ticket_type.lower():
            self.tip.required = False
            self.tip.label = "Tip (optional)"
        else:
            self.tip.required = True
            self.tip.label = "Tip (required for trades $50+)"

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cog = interaction.client.get_cog("TicketBot")
        if cog:
            await cog.process_ticket_form(interaction, self.ticket_type, self.your_side.value, 
                                        self.their_side.value, self.their_id.value, self.tip.value)

class TicketPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())

class TicketTypeSelect(ui.Select):
    def __init__(self):
        options = [
            SelectOption(label="Trial Middleman - Between 0$-$25/0-6K Rbx", value="trial_middleman"),
            SelectOption(label="Novice Middleman - Between 25$-$50/6K-12K Rbx", value="novice_middleman"),
            SelectOption(label="Advanced Middleman - Between 50$-$75/12K-18K Rbx", value="advanced_middleman"),
            SelectOption(label="Expert Middleman - Between 75$-$100/18K-25K Rbx", value="expert_middleman"),
            SelectOption(label="Senior Middleman - Between 100$-$150/25K-35K Rbx", value="senior_middleman"),
            SelectOption(label="Head Middleman - No Limit or Above 150$/35K Rbx", value="head_middleman")
        ]
        super().__init__(
            placeholder="Select middleman service needed...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_type_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(TicketForm(self.values[0]))

class TranscriptView(discord.ui.View):
    def __init__(self, html_url):
        super().__init__()
        self.add_item(discord.ui.Button(label="🌐 View Online", url=html_url, style=discord.ButtonStyle.link))

class TicketControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Close Ticket", style=ButtonStyle.red, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        cog = interaction.client.get_cog("TicketBot")
        if cog:
            await cog.close_ticket(interaction)
    
    @ui.button(label="Transcript", style=ButtonStyle.blurple, custom_id="generate_transcript")
    async def generate_transcript(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        cog = interaction.client.get_cog("TicketBot")
        if cog:
            await cog.generate_transcript_button(interaction)
    
    @ui.button(label="Delete", style=ButtonStyle.grey, custom_id="delete_ticket")
    async def delete_ticket(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        cog = interaction.client.get_cog("TicketBot")
        if cog:
            await cog.delete_ticket(interaction)

class TicketOpenView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="Open Ticket", style=ButtonStyle.green, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        cog = interaction.client.get_cog("TicketBot")
        if cog:
            await cog.open_ticket_button(interaction)
    
    @ui.button(label="Transcript", style=ButtonStyle.blurple, custom_id="generate_transcript_closed")
    async def generate_transcript_closed(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        cog = interaction.client.get_cog("TicketBot")
        if cog:
            await cog.generate_transcript_button(interaction)
    
    @ui.button(label="Delete", style=ButtonStyle.grey, custom_id="delete_ticket_closed")
    async def delete_ticket_closed(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        cog = interaction.client.get_cog("TicketBot")
        if cog:
            await cog.delete_ticket(interaction)

class TicketBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ticket_category_name = "TICKETS"
        self.transcripts_channel_name = "ticket-transcripts"
        self.support_roles = {
            "trial_middleman": "Trial Middleman",
            "novice_middleman": "Novice Middleman", 
            "advanced_middleman": "Advanced Middleman",
            "expert_middleman": "Expert Middleman",
            "senior_middleman": "Senior Middleman",
            "head_middleman": "Head Middleman"

        }
        self.ticket_counter = 1
        self.TICKET_CATEGORY_ID = None
        self.ticket_members: Dict[int, List[int]] = {}
        
        # Transcripts directory setup
        self.transcripts_dir = Path("transcripts")
        self._ensure_directory(self.transcripts_dir)
        self.website_url = os.environ.get("WEBSITE_URL", "https://xiangw-transcripts.onrender.com")
        
        if self.website_url.endswith('/'):
            self.website_url = self.website_url[:-1]

    def _ensure_directory(self, path):
        """Safely create directory if it doesn't exist"""
        try:
            path.mkdir(exist_ok=True)
        except FileExistsError:
            if not path.is_dir():
                print(f"Warning: {path} exists but is not a directory!")
        except Exception as e:
            print(f"Error creating directory {path}: {e}")

    async def cog_load(self):
        self.bot.add_view(TicketPanelView())
        self.bot.add_view(TicketControlView())
        self.bot.add_view(TicketOpenView())

    async def is_ticket_channel(self, channel: discord.TextChannel) -> bool:
        if not channel.category:
            return False
        if self.TICKET_CATEGORY_ID is None:
            category = discord.utils.get(channel.guild.categories, name=self.ticket_category_name)
            if category:
                self.TICKET_CATEGORY_ID = category.id
        return channel.category and channel.category.id == self.TICKET_CATEGORY_ID

    async def has_permission(self, member: discord.Member) -> bool:
        if member.guild_permissions.administrator:
            return True
        for role_name in self.support_roles.values():
            support_role = discord.utils.get(member.guild.roles, name=role_name)
            if support_role and support_role in member.roles:
                return True
        return False

    async def create_html_transcript(self, channel: discord.TextChannel) -> str:
        """Create HTML transcript content"""
        messages = []
        async for message in channel.history(limit=None, oldest_first=True):
            messages.append({
                "timestamp": message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                "author": message.author.display_name,
                "content": message.clean_content,
                "attachments": [{"url": att.url, "filename": att.filename} 
                               for att in message.attachments]
            })
        
        # Generate HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Transcript #{channel.name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #eee; padding-bottom: 20px; }}
        .message {{ margin: 15px 0; padding: 15px; border-left: 4px solid #007bff; background: #f8f9fa; border-radius: 4px; }}
        .timestamp {{ color: #6c757d; font-size: 0.9em; margin-bottom: 5px; }}
        .author {{ font-weight: bold; color: #495057; }}
        .content {{ margin: 5px 0; line-height: 1.5; }}
        .attachments {{ margin-top: 10px; }}
        .attachment {{ display: block; color: #007bff; text-decoration: none; margin: 5px 0; }}
        .attachment:hover {{ text-decoration: underline; }}
        .back-link {{ display: inline-block; margin-top: 20px; color: #6c757d; text-decoration: none; }}
        .back-link:hover {{ color: #495057; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Transcript #{channel.name}</h1>
            <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <a href="/" class="back-link">← Back to all transcripts</a>
        </div>
        <div class="messages">
"""
        
        for msg in messages:
            attachments_html = ""
            if msg['attachments']:
                attachments_html = '<div class="attachments">' + \
                    ''.join(f'<a href="{att["url"]}" class="attachment" target="_blank">📎 {att["filename"]}</a>' 
                            for att in msg['attachments']) + \
                    '</div>'
            
            html += f"""
            <div class="message">
                <div class="timestamp">{msg['timestamp']}</div>
                <div class="author">{msg['author']}</div>
                <div class="content">{msg['content']}</div>
                {attachments_html}
            </div>
            """
        
        html += """
        </div>
    </div>
</body>
</html>
"""
        return html

    async def generate_transcript(self, channel: discord.TextChannel):
        """Generate HTML transcript and save to directory"""
        try:
            # Generate HTML content
            html_content = await self.create_html_transcript(channel)
            
            # Create filename
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            html_filename = f"transcript-{channel.name}-{timestamp}.html"
            
            html_filepath = self.transcripts_dir / html_filename
            
            # Ensure directory exists
            self.transcripts_dir.mkdir(exist_ok=True)
            
            # Save file
            with open(html_filepath, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            print(f"Saved file: {html_filepath}")
            print(f"Files in transcripts directory: {[f.name for f in self.transcripts_dir.glob('*')]}")

            # Verify file was created
            if html_filepath.exists():
                print(f"✅ File successfully created: {html_filepath}")
                print(f"✅ File size: {html_filepath.stat().st_size} bytes")
            else:
                print(f"❌ File was not created: {html_filepath}")
            
            # Return URL and filename
            html_url = f"{self.website_url}/transcripts/{html_filename}"
            print(f"✅ Generated URL: {html_url}")
            
            return html_url, html_filename
            
        except Exception as e:
            print(f"Error generating transcript: {e}")
            return None, None

    async def send_to_transcripts_channel(self, ctx, html_url, html_filename):
        """Send HTML transcript to the dedicated transcripts channel with embed and button"""
        try:
            transcripts_channel = discord.utils.get(ctx.guild.text_channels, name=self.transcripts_channel_name)
            if not transcripts_channel:
                print(f"Transcripts channel '{self.transcripts_channel_name}' not found!")
                return False
            
            # Create embed
            embed = discord.Embed(
                title=f"📝 Transcript for #{ctx.channel.name}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="🌐 Online Version", value=f"[Click here]({html_url})", inline=True)
            embed.add_field(name="📁 File", value="Download HTML version below", inline=True)
            embed.add_field(name="🗓️ Generated", value=f"<t:{int(datetime.now().timestamp())}:R>", inline=False)
            embed.set_footer(text=f"Channel ID: {ctx.channel.id}")
            
            # Send embed with button and file
            await transcripts_channel.send(
                embed=embed,
                view=TranscriptView(html_url),
                file=discord.File(self.transcripts_dir / html_filename, filename=html_filename)
            )
            return True
            
        except Exception as e:
            print(f"Error sending to transcripts channel: {e}")
            return False

    async def send_to_transcripts_channel_interaction(self, interaction, html_url, html_filename):
        """Send HTML transcript to the dedicated transcripts channel with embed and button (for interactions)"""
        try:
            transcripts_channel = discord.utils.get(interaction.guild.text_channels, name=self.transcripts_channel_name)
            if not transcripts_channel:
                print(f"Transcripts channel '{self.transcripts_channel_name}' not found!")
                return False
            
            # Create embed
            embed = discord.Embed(
                title=f"📝 Transcript for #{interaction.channel.name}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            
            embed.add_field(name="🌐 Online Version", value=f"[Click here]({html_url})", inline=True)
            embed.add_field(name="📁 File", value="Download HTML version below", inline=True)
            embed.add_field(name="🗓️ Generated", value=f"<t:{int(datetime.now().timestamp())}:R>", inline=False)
            embed.set_footer(text=f"Channel ID: {interaction.channel.id} | Generated by {interaction.user.display_name}")
            
            # Send embed with button and file
            await transcripts_channel.send(
                embed=embed,
                view=TranscriptView(html_url),
                file=discord.File(self.transcripts_dir / html_filename, filename=html_filename)
            )
            return True
            
        except Exception as e:
            print(f"Error sending to transcripts channel: {e}")
            return False

    async def handle_transcript_generation(self, ctx_or_interaction, is_interaction=False):
        """Handle transcript generation for both commands and buttons"""
        try:
            if is_interaction:
                channel = ctx_or_interaction.channel
                send_response = ctx_or_interaction.followup.send
            else:
                channel = ctx_or_interaction.channel
                send_response = ctx_or_interaction.send
            
            # Generate transcript
            html_url, html_filename = await self.generate_transcript(channel)
            
            if not html_url:
                await send_response("❌ Failed to generate transcript.", ephemeral=is_interaction)
                return
            
            # Send to transcripts channel
            if is_interaction:
                success = await self.send_to_transcripts_channel_interaction(ctx_or_interaction, html_url, html_filename)
            else:
                success = await self.send_to_transcripts_channel(ctx_or_interaction, html_url, html_filename)
            
            if success:
                await send_response(
                    f"✅ Transcript generated and sent to <#{self._get_transcripts_channel_id(ctx_or_interaction.guild)}>!",
                    ephemeral=is_interaction
                )
            else:
                await send_response(
                    "✅ Transcript generated locally, but couldn't send to transcripts channel.",
                    ephemeral=is_interaction
                )
                
        except Exception as e:
            error_msg = f"❌ Error generating transcript: {str(e)}"
            if is_interaction:
                await ctx_or_interaction.followup.send(error_msg, ephemeral=True)
            else:
                await ctx_or_interaction.send(error_msg, delete_after=15)

    def _get_transcripts_channel_id(self, guild):
        """Get the transcripts channel ID"""
        channel = discord.utils.get(guild.text_channels, name=self.transcripts_channel_name)
        return channel.id if channel else 0

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def panel(self, ctx):
        embed = discord.Embed(
            title="Middleman Services",
            description="Select the type of middleman service you need:\n\n"
                      "• Trial Middleman - Between 0$-$25/0-6K Rbx\n"
                      "• Novice Middleman - Between 25$-$50/6K-12K Rbx\n"
                      "• Advanced Middleman - Between 50$-$75/12K-18K Rbx\n"
                      "• Expert Middleman - Between 75$-$100/18K-25K Rbx\n"
                      "• Senior Middleman - Between 100$-$150/25K-35K Rbx\n"
                      "• Head Middleman - No Limit or Above 150$/35K Rbx",

        )
        await ctx.send(embed=embed, view=TicketPanelView())

    async def process_ticket_form(self, interaction: discord.Interaction, ticket_type: str, 
                                your_side: str, their_side: str, their_id: str, tip: str = None):
        category = discord.utils.get(interaction.guild.categories, name=self.ticket_category_name)
        if not category:
            await interaction.followup.send("Ticket system not configured. Use `$setup` first.", ephemeral=True)
            return

        role_name = self.support_roles.get(ticket_type)
        if not role_name:
            await interaction.followup.send("Invalid ticket type selected.", ephemeral=True)
            return

        try:
            their_id = int(their_id)
            other_user = interaction.guild.get_member(their_id)
            if not other_user:
                await interaction.followup.send("Couldn't find that user in this server.", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("Invalid user ID format. Please provide a numeric Discord ID.", ephemeral=True)
            return

        channel_name = f"{ticket_type}-{self.ticket_counter}"
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            other_user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            interaction.guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
        }
        
        for role in self.support_roles.values():
            support_role = discord.utils.get(interaction.guild.roles, name=role)
            if support_role:
                overwrites[support_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

        ticket_channel = await category.create_text_channel(
            channel_name,
            overwrites=overwrites
        )
        self.ticket_counter += 1
        self.TICKET_CATEGORY_ID = category.id
        self.ticket_members[ticket_channel.id] = [interaction.user.id, other_user.id]

        ping_roles = []
        for role in self.support_roles.values():
            discord_role = discord.utils.get(interaction.guild.roles, name=role)
            if discord_role:
                ping_roles.append(discord_role.mention)
        
        trade_embed = discord.Embed(
            title="New Middleman Request",
            color=discord.Color.blue()
        )
        trade_embed.add_field(name=f"{interaction.user.display_name}'s side", value=your_side, inline=False)
        trade_embed.add_field(name=f"{other_user.display_name}'s side", value=their_side, inline=False)
        trade_embed.add_field(name="Their User", value=f"{other_user.mention} (ID: {their_id})", inline=False)
        if tip:
            trade_embed.add_field(name="Tip", value=tip, inline=False)
        
        trade_embed.set_footer(text=f"Ticket created by {interaction.user.display_name}")
        
        await ticket_channel.send(
            f"{interaction.user.mention} has requested a middleman service with {other_user.mention}!\n"
            + " ".join(ping_roles),
            embed=trade_embed
        )
        
        await ticket_channel.send(view=TicketControlView())
        await interaction.followup.send(f"Created your ticket: {ticket_channel.mention}", ephemeral=True)

    @commands.command(name="rename")
    @commands.has_any_role("Trial Middleman", "Novice Middleman", "Advanced Middleman","Expert Middleman","Senior Middleman", "Head Middleman", "Middleman Team")
    async def rename(self, ctx, *, new_name: str):
        """Rename the current ticket channel to exactly what is specified"""
        if not await self.is_ticket_channel(ctx.channel):
            await ctx.send("❌ This command can only be used in ticket channels.", delete_after=10)
            return

        # Clean the name to meet Discord's requirements while preserving as much as possible
        cleaned_name = new_name.lower().replace(' ', '-')
        cleaned_name = re.sub(r'[^a-z0-9\-_]', '', cleaned_name)
        cleaned_name = cleaned_name[:32]
        
        try:
            await ctx.channel.edit(name=cleaned_name)
            await ctx.send(f"✅ Ticket renamed to: `{cleaned_name}`")
        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to rename this channel.")
        except discord.HTTPException as e:
            await ctx.send(f"❌ Failed to rename channel: {e}")

    @commands.command()
    async def add(self, ctx, member: discord.Member):
        if not await self.is_ticket_channel(ctx.channel):
            await ctx.send("Not a ticket channel.", delete_after=10)
            return
        if not await self.has_permission(ctx.author):
            await ctx.send("You don't have permission.", delete_after=10)
            return

        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        if member.id not in self.ticket_members.get(ctx.channel.id, []):
            self.ticket_members.setdefault(ctx.channel.id, []).append(member.id)
        await ctx.send(f"Added {member.mention} to ticket.")

    @commands.command()
    async def remove(self, ctx, member: discord.Member):
        if not await self.is_ticket_channel(ctx.channel):
            await ctx.send("Not a ticket channel.", delete_after=10)
            return
        if not await self.has_permission(ctx.author):
            await ctx.send("You don't have permission.", delete_after=10)
            return

        await ctx.channel.set_permissions(member, read_messages=False, send_messages=False)
        if ctx.channel.id in self.ticket_members and member.id in self.ticket_members[ctx.channel.id]:
            self.ticket_members[ctx.channel.id].remove(member.id)
        await ctx.send(f"Removed {member.mention} from ticket.")

    @commands.command()
    async def open(self, ctx):
        if not await self.is_ticket_channel(ctx.channel):
            await ctx.send("Not a ticket channel.", delete_after=10)
            return
        if not await self.has_permission(ctx.author):
            await ctx.send("You don't have permission.", delete_after=10)
            return

        if ctx.channel.id in self.ticket_members:
            for member_id in self.ticket_members[ctx.channel.id]:
                member = ctx.guild.get_member(member_id)
                if member:
                    await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        
        for role_name in self.support_roles.values():
            role = discord.utils.get(ctx.guild.roles, name=role_name)
            if role:
                await ctx.channel.set_permissions(role, read_messages=True, send_messages=True)
        
        await ctx.send(f"Ticket reopened by {ctx.author.mention}", view=TicketControlView())

    async def open_ticket_button(self, interaction: discord.Interaction):
        if not await self.is_ticket_channel(interaction.channel):
            await interaction.followup.send("Not a ticket channel.", ephemeral=True)
            return
        if not await self.has_permission(interaction.user):
            await interaction.followup.send("You don't have permission.", ephemeral=True)
            return

        if interaction.channel.id in self.ticket_members:
            for member_id in self.ticket_members[interaction.channel.id]:
                member = interaction.guild.get_member(member_id)
                if member:
                    await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
        
        for role_name in self.support_roles.values():
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role:
                await interaction.channel.set_permissions(role, read_messages=True, send_messages=True)
        
        await interaction.channel.send(f"Ticket reopened by {interaction.user.mention}", view=TicketControlView())
        await interaction.followup.send("Ticket reopened.", ephemeral=True)

    @commands.command()
    async def close(self, ctx):
        if not await self.is_ticket_channel(ctx.channel):
            await ctx.send("Not a ticket channel.", delete_after=10)
            return
        if not await self.has_permission(ctx.author):
            await ctx.send("You don't have permission.", delete_after=10)
            return

        embed = discord.Embed(
            title="Ticket Closed",
            description=f"Closed by {ctx.author.mention}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, view=TicketOpenView())
        
        for member in ctx.guild.members:
            if not await self.has_permission(member) and member != ctx.guild.me:
                await ctx.channel.set_permissions(member, read_messages=False, send_messages=False)

    async def close_ticket(self, interaction: discord.Interaction):
        if not await self.is_ticket_channel(interaction.channel):
            await interaction.followup.send("Not a ticket channel.", ephemeral=True)
            return
        if not await self.has_permission(interaction.user):
            await interaction.followup.send("You don't have permission.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Ticket Closed",
            description=f"Closed by {interaction.user.mention}",
            color=discord.Color.red()
        )
        await interaction.channel.send(embed=embed, view=TicketOpenView())
        
        for member in interaction.guild.members:
            if not await self.has_permission(member) and member != interaction.guild.me:
                await interaction.channel.set_permissions(member, read_messages=False, send_messages=False)
        
        await interaction.followup.send("Ticket closed.", ephemeral=True)

    async def generate_transcript_button(self, interaction: discord.Interaction):
        """Button handler for generating transcripts - shows only one ephemeral message"""
        if not await self.is_ticket_channel(interaction.channel):
            await interaction.followup.send("Not a ticket channel.", ephemeral=True)
            return
        if not await self.has_permission(interaction.user):
            await interaction.followup.send("You don't have permission.", ephemeral=True)
            return

        await interaction.followup.send("🔄 Generating transcript...", ephemeral=True)
        await self.handle_transcript_generation(interaction, is_interaction=True)

    @commands.command()
    @commands.has_any_role("Trial Middleman", "Novice Middleman", "Advanced Middleman","Expert Middleman","Senior Middleman", "Head Middleman", "Middleman Team")
    async def transcript(self, ctx):
        """Generate transcript and provide link"""
        if not await self.is_ticket_channel(ctx.channel):
            return await ctx.send("❌ This command can only be used in ticket channels.", delete_after=10)
        
        msg = await ctx.send("🔄 Generating transcript...")
        await self.handle_transcript_generation(ctx, is_interaction=False)
        await msg.delete()

    @commands.command()
    async def delete(self, ctx):
        if not await self.is_ticket_channel(ctx.channel):
            await ctx.send("Not a ticket channel.", delete_after=10)
            return
        if not await self.has_permission(ctx.author):
            await ctx.send("You don't have permission.", delete_after=10)
            return

        try:
            # Generate transcript first
            transcript_msg = await ctx.send("🔄 Generating transcript before deletion...")
            html_url, html_filename = await self.generate_transcript(ctx.channel)
            
            if html_url:
                # Send to transcripts channel
                success = await self.send_to_transcripts_channel(ctx, html_url, html_filename)
                if success:
                    await ctx.send(f"✅ Transcript saved to <#{self._get_transcripts_channel_id(ctx.guild)}>")
                else:
                    await ctx.send("✅ Transcript generated locally")
            else:
                await ctx.send("❌ Failed to generate transcript, but will proceed with deletion.")
            
            # Add 5-second delay before deletion
            await ctx.send("🗑️ Channel will be deleted in 5 seconds...")
            await asyncio.sleep(5)
            
            # Delete the channel
            if ctx.channel.id in self.ticket_members:
                del self.ticket_members[ctx.channel.id]
            await ctx.channel.delete()
            
        except Exception as e:
            await ctx.send(f"❌ Error during deletion: {e}")

    async def delete_ticket(self, interaction: discord.Interaction):
        if not await self.is_ticket_channel(interaction.channel):
            await interaction.followup.send("Not a ticket channel.", ephemeral=True)
            return
        if not await self.has_permission(interaction.user):
            await interaction.followup.send("You don't have permission.", ephemeral=True)
            return

        try:
            # Generate transcript first
            await interaction.followup.send("🔄 Generating transcript before deletion...", ephemeral=True)
            html_url, html_filename = await self.generate_transcript(interaction.channel)
            
            if html_url:
                # Send to transcripts channel
                success = await self.send_to_transcripts_channel_interaction(interaction, html_url, html_filename)
                if success:
                    await interaction.followup.send(
                        f"✅ Transcript saved to <#{self._get_transcripts_channel_id(interaction.guild)}>",
                        ephemeral=True
                    )
                else:
                    await interaction.followup.send("✅ Transcript generated locally", ephemeral=True)
            else:
                await interaction.followup.send("❌ Failed to generate transcript, but will proceed with deletion.", ephemeral=True)
            
            # Add 5-second delay before deletion
            await interaction.channel.send("🗑️ Channel will be deleted in 5 seconds...")
            await asyncio.sleep(5)
            
            # Delete the channel
            if interaction.channel.id in self.ticket_members:
                del self.ticket_members[interaction.channel.id]
            await interaction.channel.delete()
            
        except Exception as e:
            await interaction.followup.send(f"❌ Error during deletion: {e}", ephemeral=True)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def setup(self, ctx):
        created_roles = []
        for role_key, role_name in self.support_roles.items():
            if not discord.utils.get(ctx.guild.roles, name=role_name):
                try:
                    role = await ctx.guild.create_role(
                        name=role_name,
                        color=discord.Color.blue(),
                        permissions=discord.Permissions(
                            manage_channels=True,
                            manage_messages=True,
                            read_message_history=True
                        ),
                        reason="Ticket system setup"
                    )
                    created_roles.append(role.mention)
                except Exception as e:
                    await ctx.send(f"Failed to create {role_name}: {e}")
            else:
                created_roles.append(f"@{role_name} (exists)")

        category = discord.utils.get(ctx.guild.categories, name=self.ticket_category_name)
        if not category:
            try:
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    ctx.guild.me: discord.PermissionOverwrite(read_messages=True, manage_channels=True)
                }
                for role_name in self.support_roles.values():
                    role = discord.utils.get(ctx.guild.roles, name=role_name)
                    if role:
                        overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

                category = await ctx.guild.create_category(
                    name=self.ticket_category_name,
                    overwrites=overwrites,
                    reason="Ticket system setup"
                )
                self.TICKET_CATEGORY_ID = category.id
                await ctx.send(f"Created ticket category: {category.name}")
            except Exception as e:
                await ctx.send(f"Failed to create category: {e}")
                return

        if not discord.utils.get(ctx.guild.text_channels, name=self.transcripts_channel_name):
            try:
                overwrites = {
                    ctx.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                    ctx.guild.me: discord.PermissionOverwrite(read_messages=True)
                }
                for role_name in self.support_roles.values():
                    role = discord.utils.get(ctx.guild.roles, name=role_name)
                    if role:
                        overwrites[role] = discord.PermissionOverwrite(read_messages=True)

                transcripts_channel = await category.create_text_channel(
                    name=self.transcripts_channel_name,
                    overwrites=overwrites,
                    reason="Ticket system setup"
                )
                await ctx.send(f"Created transcripts channel: {transcripts_channel.mention}")
            except Exception as e:
                await ctx.send(f"Failed to create transcripts channel: {e}")
                return

        await ctx.send(
            "Ticket system setup complete!\n"
            f"Roles: {', '.join(created_roles)}\n"
            "Assign these roles to your middleman team."
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        # Ignore the bot's own messages
        if message.author == self.bot.user:
            return
        
        # Handle DMs
        if isinstance(message.channel, discord.DMChannel):
            await message.channel.send(
                "**❗ We do not handle matters in DMs. Please proceed to this server instead: " \
                "https://discord.gg/Y65BzWuCUU **"
            )
            return

        if message.content.startswith("$calc"):
            user_id = message.author.id
            now = time.time()
            
            # Check cooldown
            if user_id in user_cooldowns and now < user_cooldowns[user_id]:
                remaining = user_cooldowns[user_id] - now
                await message.channel.send(f"⚠️ Please wait {remaining:.1f} seconds before using this command again.")
                return
            
            expr = message.content[5:].strip()
            try:
                result = eval(expr, {"__builtins__": None}, {"math": math})
            except Exception:
                await message.channel.send("⚠️ Invalid expression.")
                return
            
            await message.channel.send(f"Result: `{result}`")
            # Set cooldown
            user_cooldowns[user_id] = now + COOLDOWN_SECONDS

async def setup(bot):
    await bot.add_cog(TicketBot(bot))

async def main():
    # Get token from system environment variables
    bot_token = os.environ.get("DISCORD_BOT_TOKEN")
    
    if not bot_token:
        print("Error: DISCORD_BOT_TOKEN environment variable not set")
        print("Set it with: export DISCORD_BOT_TOKEN='your_token_here'")
        exit(1)
    
    await setup(bot)
    await bot.start(bot_token)

if __name__ == "__main__":
    asyncio.run(main())
