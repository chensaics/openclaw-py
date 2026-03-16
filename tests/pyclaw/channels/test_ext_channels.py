"""Tests for extension channels -- basic instantiation and message helpers."""

from __future__ import annotations

from pyclaw.channels.base import ChannelPlugin


class TestIRCChannel:
    def test_is_channel_plugin(self):
        from pyclaw.channels.irc.channel import IrcChannel

        assert issubclass(IrcChannel, ChannelPlugin)

    def test_chunk_text(self):
        from pyclaw.channels.irc.channel import _chunk_text

        text = "Hello world " * 100
        chunks = _chunk_text(text, 350)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 350


class TestMSTeamsChannel:
    def test_is_channel_plugin(self):
        from pyclaw.channels.msteams.channel import MSTeamsChannel

        assert issubclass(MSTeamsChannel, ChannelPlugin)


class TestMatrixChannel:
    def test_is_channel_plugin(self):
        from pyclaw.channels.matrix.channel import MatrixChannel

        assert issubclass(MatrixChannel, ChannelPlugin)


class TestFeishuChannel:
    def test_is_channel_plugin(self):
        from pyclaw.channels.feishu.channel import FeishuChannel

        assert issubclass(FeishuChannel, ChannelPlugin)


class TestTwitchChannel:
    def test_is_channel_plugin(self):
        from pyclaw.channels.twitch.channel import TwitchChannel

        assert issubclass(TwitchChannel, ChannelPlugin)


class TestBlueBubblesChannel:
    def test_is_channel_plugin(self):
        from pyclaw.channels.bluebubbles.channel import BlueBubblesChannel

        assert issubclass(BlueBubblesChannel, ChannelPlugin)


class TestGoogleChatChannel:
    def test_is_channel_plugin(self):
        from pyclaw.channels.googlechat.channel import GoogleChatChannel

        assert issubclass(GoogleChatChannel, ChannelPlugin)
