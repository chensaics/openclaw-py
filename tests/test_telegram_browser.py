"""Tests for Phase 22 — Telegram enhanced, browser relay, and link understanding."""

from __future__ import annotations

from pyclaw.agents.link_understanding import (
    LinkMetadata,
    classify_url_content_type,
    extract_urls,
    format_link_context,
    format_multiple_links,
    is_fetchable_url,
    parse_og_metadata,
)
from pyclaw.browser.relay import (
    BrowserRelayManager,
    RelayConfig,
    RelayState,
    validate_cors_origin,
    validate_relay_auth,
)
from pyclaw.channels.telegram.enhanced import (
    ChatActionBackoff,
    chunk_telegram_message,
    escape_markdown_v2,
    extract_reply_media_context,
    markdown_to_telegram_html,
)

# ===== Telegram Enhanced =====


class TestReplyMediaContext:
    def test_photo(self) -> None:
        reply = {
            "photo": [
                {"file_id": "small", "file_size": 100, "width": 50, "height": 50},
                {"file_id": "large", "file_size": 5000, "width": 800, "height": 600},
            ],
            "caption": "A photo",
        }
        ctx = extract_reply_media_context(reply)
        assert ctx is not None
        assert ctx.media_type == "photo"
        assert ctx.file_id == "large"
        assert ctx.caption == "A photo"

    def test_document(self) -> None:
        reply = {
            "document": {
                "file_id": "doc1",
                "file_name": "test.pdf",
                "mime_type": "application/pdf",
                "file_size": 10000,
            },
        }
        ctx = extract_reply_media_context(reply)
        assert ctx is not None
        assert ctx.media_type == "document"
        assert ctx.file_name == "test.pdf"

    def test_audio(self) -> None:
        reply = {
            "audio": {
                "file_id": "aud1",
                "duration": 120,
                "mime_type": "audio/mpeg",
            },
        }
        ctx = extract_reply_media_context(reply)
        assert ctx is not None
        assert ctx.media_type == "audio"
        assert ctx.duration == 120

    def test_video(self) -> None:
        reply = {
            "video": {
                "file_id": "vid1",
                "width": 1920,
                "height": 1080,
                "duration": 60,
            },
        }
        ctx = extract_reply_media_context(reply)
        assert ctx is not None
        assert ctx.media_type == "video"

    def test_voice(self) -> None:
        reply = {"voice": {"file_id": "v1", "duration": 5}}
        ctx = extract_reply_media_context(reply)
        assert ctx is not None
        assert ctx.media_type == "voice"

    def test_sticker(self) -> None:
        reply = {"sticker": {"file_id": "s1", "width": 512, "height": 512}}
        ctx = extract_reply_media_context(reply)
        assert ctx is not None
        assert ctx.media_type == "sticker"

    def test_no_media(self) -> None:
        reply = {"text": "Just text"}
        assert extract_reply_media_context(reply) is None

    def test_empty(self) -> None:
        assert extract_reply_media_context({}) is None
        assert extract_reply_media_context(None) is None


class TestChunkTelegramMessage:
    def test_short_message(self) -> None:
        chunks = chunk_telegram_message("Hello")
        assert chunks == ["Hello"]

    def test_long_message(self) -> None:
        text = "a" * 8000
        chunks = chunk_telegram_message(text)
        assert len(chunks) >= 2
        assert all(len(c) <= 4096 for c in chunks)

    def test_paragraph_split(self) -> None:
        text = "Paragraph one.\n\nParagraph two.\n\n" + "x" * 4200
        chunks = chunk_telegram_message(text)
        assert len(chunks) >= 2


class TestMarkdownV2Escape:
    def test_special_chars(self) -> None:
        result = escape_markdown_v2("Hello *world* [link](url)")
        assert "\\*" in result
        assert "\\[" in result
        assert "\\(" in result

    def test_plain_text(self) -> None:
        assert escape_markdown_v2("Hello world") == "Hello world"


class TestMarkdownToTelegramHtml:
    def test_bold(self) -> None:
        assert "<b>bold</b>" in markdown_to_telegram_html("**bold**")

    def test_italic(self) -> None:
        result = markdown_to_telegram_html("*italic*")
        assert "<i>" in result

    def test_code(self) -> None:
        result = markdown_to_telegram_html("`code`")
        assert "<code>" in result

    def test_link(self) -> None:
        result = markdown_to_telegram_html("[click](https://x.com)")
        assert '<a href="https://x.com">' in result


class TestChatActionBackoff:
    def test_initially_allowed(self) -> None:
        backoff = ChatActionBackoff()
        assert backoff.should_send("c1") is True

    def test_suppressed_after_429(self) -> None:
        backoff = ChatActionBackoff(base_delay_s=100)
        backoff.record_failure("c1", status_code=429)
        assert backoff.should_send("c1") is False

    def test_suppressed_after_consecutive(self) -> None:
        backoff = ChatActionBackoff(max_consecutive=2, base_delay_s=100)
        backoff.record_failure("c1")
        backoff.record_failure("c1")
        assert backoff.should_send("c1") is False

    def test_success_resets(self) -> None:
        backoff = ChatActionBackoff(max_consecutive=2, base_delay_s=100)
        backoff.record_failure("c1")
        backoff.record_success("c1")
        backoff.record_failure("c1")
        assert backoff.should_send("c1") is True

    def test_reset(self) -> None:
        backoff = ChatActionBackoff(max_consecutive=1, base_delay_s=100)
        backoff.record_failure("c1")
        backoff.reset("c1")
        assert backoff.should_send("c1") is True


# ===== Browser Relay =====


class TestCorsValidation:
    def test_chrome_extension(self) -> None:
        assert (
            validate_cors_origin(
                "chrome-extension://abcdef123456",
                ["chrome-extension://"],
            )
            is True
        )

    def test_rejected_origin(self) -> None:
        assert validate_cors_origin("https://evil.com", ["chrome-extension://"]) is False

    def test_empty_origin(self) -> None:
        assert validate_cors_origin("", ["chrome-extension://"]) is False

    def test_exact_match(self) -> None:
        assert validate_cors_origin("https://app.openclaw.ai", ["https://app.openclaw.ai"]) is True


class TestRelayAuth:
    def test_valid_token(self) -> None:
        assert validate_relay_auth("secret123", "secret123") is True

    def test_invalid_token(self) -> None:
        assert validate_relay_auth("wrong", "secret123") is False

    def test_no_auth_configured(self) -> None:
        assert validate_relay_auth("anything", "") is True


class TestBrowserRelayManager:
    def test_create_session(self) -> None:
        mgr = BrowserRelayManager(RelayConfig(allowed_origins=["chrome-extension://"]))
        session = mgr.create_session(origin="chrome-extension://abc")
        assert session is not None
        assert session.state == RelayState.CONNECTING

    def test_reject_bad_origin(self) -> None:
        mgr = BrowserRelayManager(RelayConfig(allowed_origins=["chrome-extension://"]))
        session = mgr.create_session(origin="https://evil.com")
        assert session is None

    def test_authenticate(self) -> None:
        mgr = BrowserRelayManager(RelayConfig(auth_token="secret"))
        session = mgr.create_session()
        assert session is not None
        assert mgr.authenticate_session(session.session_id, "secret") is True
        assert session.authenticated is True

    def test_auth_failure(self) -> None:
        mgr = BrowserRelayManager(RelayConfig(auth_token="secret"))
        session = mgr.create_session()
        assert session is not None
        assert mgr.authenticate_session(session.session_id, "wrong") is False

    def test_max_sessions(self) -> None:
        mgr = BrowserRelayManager(RelayConfig(max_sessions=2))
        mgr.create_session()
        mgr.create_session()
        assert mgr.create_session() is None

    def test_heartbeat(self) -> None:
        mgr = BrowserRelayManager(RelayConfig(auth_token=""))
        session = mgr.create_session()
        assert session is not None
        mgr.authenticate_session(session.session_id, "")
        assert mgr.handle_heartbeat(session.session_id) is True

    def test_disconnect(self) -> None:
        mgr = BrowserRelayManager()
        session = mgr.create_session()
        assert session is not None
        mgr.disconnect_session(session.session_id)
        assert mgr.session_count == 0

    def test_reconnect_delay(self) -> None:
        mgr = BrowserRelayManager(RelayConfig(reconnect_delay_s=5))
        session = mgr.create_session()
        assert session is not None
        delay = mgr.compute_reconnect_delay(session.session_id)
        assert delay >= 5


# ===== Link Understanding =====


class TestExtractUrls:
    def test_single_url(self) -> None:
        urls = extract_urls("Check out https://example.com")
        assert urls == ["https://example.com"]

    def test_multiple_urls(self) -> None:
        urls = extract_urls("See https://a.com and https://b.com")
        assert len(urls) == 2

    def test_deduplicate(self) -> None:
        urls = extract_urls("https://a.com and https://a.com again")
        assert len(urls) == 1

    def test_strip_trailing_punctuation(self) -> None:
        urls = extract_urls("Visit https://example.com.")
        assert urls == ["https://example.com"]

    def test_no_urls(self) -> None:
        assert extract_urls("No links here") == []


class TestClassifyUrlContentType:
    def test_image(self) -> None:
        assert classify_url_content_type("https://x.com/photo.jpg") == "image"

    def test_video_extension(self) -> None:
        assert classify_url_content_type("https://x.com/clip.mp4") == "video"

    def test_youtube(self) -> None:
        assert classify_url_content_type("https://youtube.com/watch?v=abc") == "video"

    def test_article(self) -> None:
        assert classify_url_content_type("https://blog.com/post") == "article"

    def test_pdf(self) -> None:
        assert classify_url_content_type("https://x.com/doc.pdf") == "document"


class TestIsFetchable:
    def test_article(self) -> None:
        assert is_fetchable_url("https://blog.com/post") is True

    def test_image(self) -> None:
        assert is_fetchable_url("https://x.com/photo.jpg") is False

    def test_video(self) -> None:
        assert is_fetchable_url("https://youtube.com/watch?v=abc") is False


class TestParseOgMetadata:
    def test_full_og(self) -> None:
        html = """
        <html><head>
        <meta property="og:title" content="Test Article">
        <meta property="og:description" content="A great article">
        <meta property="og:image" content="https://img.com/photo.jpg">
        <meta property="og:type" content="article">
        <meta property="og:site_name" content="TestSite">
        <title>Fallback Title</title>
        </head></html>
        """
        meta = parse_og_metadata(html, url="https://testsite.com/post")
        assert meta.title == "Test Article"
        assert meta.description == "A great article"
        assert meta.og_image == "https://img.com/photo.jpg"
        assert meta.site_name == "TestSite"
        assert meta.content_type == "article"

    def test_fallback_title(self) -> None:
        html = "<html><head><title>Page Title</title></head></html>"
        meta = parse_og_metadata(html)
        assert meta.title == "Page Title"

    def test_domain_extraction(self) -> None:
        meta = parse_og_metadata("<html></html>", url="https://www.example.com/page")
        assert meta.domain == "example.com"

    def test_video_type(self) -> None:
        html = '<meta property="og:type" content="video.other">'
        meta = parse_og_metadata(html, url="https://example.com")
        assert meta.content_type == "video"


class TestFormatLinkContext:
    def test_full_metadata(self) -> None:
        meta = LinkMetadata(
            url="https://example.com",
            title="Test",
            description="A test page",
            site_name="Example",
        )
        result = format_link_context(meta)
        assert "**Test**" in result
        assert "*Example*" in result
        assert "A test page" in result
        assert "https://example.com" in result

    def test_minimal(self) -> None:
        meta = LinkMetadata(url="https://example.com")
        result = format_link_context(meta)
        assert "https://example.com" in result

    def test_multiple_links(self) -> None:
        links = [
            LinkMetadata(url="https://a.com", title="A"),
            LinkMetadata(url="https://b.com", title="B"),
        ]
        result = format_multiple_links(links)
        assert "[Link 1]" in result
        assert "[Link 2]" in result

    def test_empty_links(self) -> None:
        assert format_multiple_links([]) == ""
