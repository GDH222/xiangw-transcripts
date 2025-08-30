import os
from pathlib import Path
from datetime import datetime

class TicketBot(commands.Cog):
    def __init__(self, bot):
        # ... existing code ...
        self.transcripts_dir = Path("static/transcripts")
        self.transcripts_dir.mkdir(exist_ok=True, parents=True)
        self.website_url = os.environ.get("WEBSITE_URL", "http://localhost:5000")

    async def generate_transcript(self, channel: discord.TextChannel):
        """Generate HTML transcript and save to static directory"""
        try:
            html_content = await self.create_html_transcript(channel)
            
            # Create filename
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            filename = f"transcript-{channel.name}-{timestamp}.html"
            filepath = self.transcripts_dir / filename
            
            # Save file
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            # Return the URL for the transcript
            transcript_url = f"{self.website_url}/transcripts/{filename}"
            return transcript_url
            
        except Exception as e:
            print(f"Error generating transcript: {e}")
            return None

    async def create_html_transcript(self, channel: discord.TextChannel) -> str:
        """Create HTML transcript content - PURE PYTHON"""
        messages = []
        async for message in channel.history(limit=None, oldest_first=True):
            # Just collect message info, no file downloads
            messages.append({
                "timestamp": message.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                "author": message.author.display_name,
                "content": message.clean_content,
                "attachments": [{"url": att.url, "filename": att.filename} 
                               for att in message.attachments]
            })
        
        # Generate HTML using Python string formatting
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

    @commands.command()
    @commands.has_any_role("Trial Middleman", "Beginner Middleman", "Advanced Middleman", "Head Middleman", "Support Team")
    async def transcript(self, ctx):
        """Generate transcript and provide link"""
        if not await self.is_ticket_channel(ctx.channel):
            return await ctx.send("❌ This command can only be used in ticket channels.", delete_after=10)
        
        try:
            msg = await ctx.send("🔄 Generating transcript...")
            
            transcript_url = await self.generate_transcript(ctx.channel)
            
            if transcript_url:
                await ctx.send(
                    f"✅ Transcript generated!\n"
                    f"🌐 View it at: {transcript_url}"
                )
            else:
                await ctx.send("❌ Failed to generate transcript.")
            
            await msg.delete()
            
        except Exception as e:
            await ctx.send(f"❌ Error generating transcript: {str(e)}", delete_after=15)
