# Textual Framework Capabilities for Sci-Fi Terminal UI

**Research Date:** 2026-02-17
**Framework Version:** Textual 3.x with Rich library
**Target:** Advanced sci-fi terminal UI effects for MoE debate system

---

## 1. Animation Capabilities

### CSS Transitions & Animations

Textual provides a powerful animation system that modifies style attributes over time:

```python
from textual.app import App, ComposeResult
from textual.widgets import Static

class AnimationApp(App):
    def compose(self) -> ComposeResult:
        self.box = Static("SYSTEM ACTIVE")
        self.box.styles.background = "red"
        yield self.box

    def on_mount(self):
        # Animate opacity over 2 seconds
        self.box.styles.animate("opacity", value=0.0, duration=2.0)

        # Animate with delay and callback
        self.box.styles.animate(
            "opacity",
            value=1.0,
            duration=1.5,
            delay=0.5,
            easing="in_out_cubic",
            on_complete=self.animation_done
        )
```

**Animatable Properties:**
- `offset` - Move widgets around the screen
- `opacity` - Fading effects (0.0 to 1.0)
- CSS styles - Any numeric CSS property

**Easing Functions:** View all with `textual easing` command
- Default: `in_out_cubic` (creates organic motion)
- Options: linear, in_out_sine, bounce, elastic, etc.

**Parameters:**
- `duration` - Total animation time in seconds
- `speed` - Units changed per second (alternative to duration)
- `delay` - Postpone animation start
- `on_complete` - Callback when finished

### Reactive Animations

Combine reactive attributes with set_interval for continuous animations:

```python
from textual.reactive import reactive
from textual.widget import Widget

class PulsingWidget(Widget):
    opacity_value = reactive(1.0)

    def on_mount(self):
        self.set_interval(0.05, self.pulse)

    def pulse(self):
        # Create pulsing/breathing effect
        current = self.opacity_value
        if current >= 1.0:
            self.direction = -1
        elif current <= 0.3:
            self.direction = 1
        self.opacity_value += 0.05 * self.direction
        self.styles.opacity = self.opacity_value
```

**Performance:** Smooth animations at up to 60 FPS on modern terminals (iTerm, Warp, Kitty).

---

## 2. Visual Effects & Rich Markup

### Built-in Renderables

Textual includes powerful renderables for advanced visuals:

#### Sparkline - Live Data Visualization
```python
from textual.renderables import Sparkline
from textual.color import Color

sparkline = Sparkline(
    data=[1, 4, 2, 8, 5, 9, 3],
    width=20,
    height=4,
    min_color=Color.from_rgb(0, 255, 0),
    max_color=Color.from_rgb(255, 0, 0),
    summary_function=max
)
```

#### LinearGradient - Directional Gradients
```python
from textual.renderables import LinearGradient

gradient = LinearGradient(
    angle=45.0,
    stops=[(0.0, "cyan"), (0.5, "magenta"), (1.0, "yellow")]
)
```

#### Bar - Progress Indicators
```python
from textual.renderables import Bar

bar = Bar(
    highlight_range=(0, 50),
    highlight_style="bright_cyan",
    background_style="grey37",
    gradient=LinearGradient(0, [(0.0, "blue"), (1.0, "red")])
)
```

#### Digits - Large Number Display
```python
from textual.renderables import Digits

large_numbers = Digits("42", style="bold cyan")
```

### Rich Library Integration

Any Rich renderable works in Textual widgets:

```python
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Rich markup in widgets
text = Text("SYSTEM STATUS: ", style="bold")
text.append("ACTIVE", style="bold green blink")

# Panels with borders
panel = Panel(
    "Neural network initialized\n[bold cyan]Agents ready[/]",
    title="[bold magenta]SYSTEM[/]",
    border_style="cyan"
)

# Tables with styling
table = Table(title="Agent Status")
table.add_column("Agent", style="cyan")
table.add_column("Status", style="magenta")
table.add_row("Agent-1", "[bold green]ACTIVE[/]")
```

### Unicode Block Characters

Create pseudo-pixel graphics with Unicode:

```python
# Vertical bar charts
blocks = "▁▂▃▄▅▆▇█"

# Horizontal bars
h_blocks = "▏▎▍▌▋▊▉█"

# Braille patterns for high-res text graphics (2800-28FF)
braille = "⠀⠁⠂⠃⠄⠅⠆⠇⠈⠉⠊⠋⠌⠍⠎⠏"

# Box drawing
boxes = "─│┌┐└┘├┤┬┴┼"
```

**Use Case:** Build sparklines, graphs, loading bars, pixel art using half-characters as pixels.

---

## 3. Color Capabilities

### True Color Support

Textual supports 24-bit RGB color:

```python
from textual.color import Color

# Multiple color formats
color1 = Color.from_rgb(255, 0, 128)
color2 = Color.from_hsl(180, 1.0, 0.5)
color3 = Color.parse("#00FF20")
color4 = Color.parse("cyan")
```

### Gradient Generation

Create smooth color gradients programmatically:

```python
from textual.color import Color

# Define gradient with stops
gradient_stops = [(0.0, Color.parse("blue")), (1.0, Color.parse("red"))]

# Calculate intermediate color at position 0.5
start_color = Color.parse("cyan")
end_color = Color.parse("magenta")
mid_color = start_color.blend(end_color, 0.5, quality=10)
```

### HSL Manipulation for Effects

HSL is perfect for programmatic color changes:

```python
def create_breathing_color(base_hsl, time_value):
    """Create pulsing effect by varying lightness"""
    h, s, l = base_hsl
    pulse = 0.3 + 0.2 * math.sin(time_value)
    return Color.from_hsl(h, s, pulse)
```

### Animated Gradients with textual-pyfiglet

```python
from textual_pyfiglet import FigletWidget

figlet = FigletWidget(
    text="NEURAL NET",
    font="banner3",
    gradient_start_color="cyan",
    gradient_end_color="magenta",
    animate=True,
    animation_speed=5,  # High speed for smooth animation
    gradient_steps=50   # High steps for smoothness
)
```

**Animation Settings:**
- Low colors + low speed = retro look
- High colors + high speed = smooth modern animation
- Can be toggled on/off in real-time

---

## 4. Layout System

### CSS Grid

```python
# In CSS file or inline
"""
#grid-container {
    layout: grid;
    grid-size: 3 2;  # 3 columns, 2 rows
    grid-gutter: 1 2;
}
"""
```

Widgets fill grid cells left-to-right, top-to-bottom.

### Fractional Units (fr)

Better than percentages for dynamic layouts:

```python
"""
#sidebar {
    width: 1fr;
}
#main {
    width: 3fr;  # 3x wider than sidebar
}
"""
```

### Layers for Z-Index Control

```python
# In widget class
LAYERS = ["base", "overlay", "top"]

# Assign widgets to layers
widget.styles.layer = "overlay"
```

### Dynamic Resize Handling

```python
def on_resize(self, event):
    """Respond to terminal size changes"""
    new_width = event.size.width
    new_height = event.size.height
    # Adjust layout dynamically
```

---

## 5. Screen Management & Modals

### Screen Stack

```python
from textual.screen import Screen, ModalScreen

class DetailScreen(Screen):
    def compose(self) -> ComposeResult:
        yield Static("Detail View")

# Push screen onto stack
self.push_screen(DetailScreen())

# Pop to return to previous
self.pop_screen()

# Switch without stacking
self.switch_screen(DetailScreen())
```

### Modal Dialogs

```python
class ConfirmDialog(ModalScreen[bool]):
    """Modal dialog that dims background and blocks input"""

    def compose(self) -> ComposeResult:
        yield Container(
            Label("Confirm action?"),
            Button("Yes", id="yes"),
            Button("No", id="no"),
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")

# Show modal with callback
def handle_response(confirmed: bool):
    if confirmed:
        self.execute_action()

self.push_screen(ConfirmDialog(), handle_response)
```

### Transparent Overlays

Screens with alpha transparency blend with screens below:

```python
"""
OverlayScreen {
    background: rgba(0, 0, 255, 0.5);  # 50% blue tint
}
"""
```

### Screen Modes

Manage multiple independent screen stacks:

```python
class MyApp(App):
    MODES = {
        "dashboard": DashboardScreen,
        "settings": SettingsScreen,
        "analysis": AnalysisScreen,
    }

    def on_mount(self):
        self.switch_mode("dashboard")
```

---

## 6. Custom Widgets & Canvas

### Canvas Widget (textual-canvas)

Character-based drawing surface:

```python
from textual_canvas import Canvas

canvas = Canvas(width=80, height=40)

# Color individual "pixels" (half-characters)
canvas.set_pixel(x=10, y=5, color="cyan")

# Scrollable and focusable
# Use for: graphs, visualizations, pixel art
```

**Projects using Canvas:**
- textual-mandelbrot - Mathematical visualizations
- Pain - MS Paint clone in terminal

### Custom Renderables

Create reusable visual components:

```python
from rich.console import Console, ConsoleOptions, RenderResult
from rich.segment import Segment

class CustomRenderable:
    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        # Generate styled segments
        yield Segment("█" * 10, Style(color="cyan"))
        yield Segment.line()
```

---

## 7. Advanced Features

### DataTable with Live Updates

```python
from textual.widgets import DataTable
from rich.text import Text

table = DataTable()
table.add_columns("Agent", "Score", "Status")

# Add row with Rich renderables
table.add_row(
    "Agent-1",
    Text("95.3", style="bold green"),
    Text("ACTIVE", style="blink cyan")
)

# Update cells in real-time
def update_scores(self):
    self.set_interval(0.1, self.refresh_data)

def refresh_data(self):
    row_key = self.table.get_row_at(0)
    self.table.update_cell(row_key, "Score", new_value)
```

### Notifications & Toasts

```python
# Application-wide notifications
self.notify(
    "System initialized",
    title="Status Update",
    severity="information",
    timeout=3.0
)

# Severities: information, warning, error
# Supports Rich markup
self.notify("[bold cyan]Agent 3[/] has joined", severity="information")
```

### Loading Indicators

```python
from textual.widgets import LoadingIndicator

# Pulsating dots animation
yield LoadingIndicator()
```

### Progress Bars

```python
from textual.widgets import ProgressBar

progress = ProgressBar(total=100, show_eta=True)

# Update progress
progress.advance(10)  # Add 10 steps

# Indeterminate mode (bouncing bar)
progress = ProgressBar()  # No total specified
```

---

## 8. Terminal Art & ASCII

### Figlet Text (textual-pyfiglet)

Large ASCII banners with color and animation:

```python
from textual_pyfiglet import FigletWidget

banner = FigletWidget(
    text="ARBITER",
    font="banner3",  # Many fonts available
    gradient_start_color="#00FFFF",
    gradient_end_color="#FF00FF",
    animate=True
)

# Change text dynamically
banner.text = "PROCESSING"
banner.font = "slant"
```

**Available fonts:** banner3, slant, standard, bigfig, cosmic, etc.

### Rich Pixels Library

Display images and pixel art:

```python
from rich_pixels import Pixels

# Load and display image
pixels = Pixels.from_image_path("logo.png")
```

### Box Drawing Composition

```python
# Create custom borders and frames
border_chars = {
    "tl": "╔", "tr": "╗", "bl": "╚", "br": "╝",
    "h": "═", "v": "║"
}

def draw_frame(width, height):
    top = border_chars["tl"] + border_chars["h"] * (width-2) + border_chars["tr"]
    mid = border_chars["v"] + " " * (width-2) + border_chars["v"]
    bot = border_chars["bl"] + border_chars["h"] * (width-2) + border_chars["br"]
    return top + "\n" + (mid + "\n") * (height-2) + bot
```

---

## 9. Performance Characteristics

### Frame Rate Capabilities

- **Modern terminals:** Up to 60 FPS (iTerm, Warp, Kitty, WezTerm)
- **GPU acceleration:** Modern terminals use GPU for text rendering
- **Textual optimization:** Partial updates - only changed regions refresh

### Widget Count Scalability

- **Spatial mapping algorithm:** Linear scaling with widget count
- **Benchmarks:** Scrolling 8 widgets takes same time as 1000+ widgets
- **Grid optimization:** 100×20 character tiles for quick visibility checks
- **Caching:** Spatial map cached during scrolling

### Smooth Animation Feasibility

**YES** - Smooth animations are highly feasible:
- Compositor does partial updates (only changed regions)
- Segment-based rendering (not character-by-character)
- Efficient caching strategies
- Quote: "smooth scrolling, even with a metric tonne of widgets on screen"

### Best Practices

1. **Use reactive attributes** for automatic UI updates
2. **Leverage compositor** - let Textual handle rendering optimization
3. **Animate styles** rather than forcing full redraws
4. **Layer widgets** strategically to minimize recomposition
5. **Cache spatial calculations** when possible

---

## 10. Impressive Textual Projects

### Development Tools

- **Harlequin** - SQL IDE for terminal with syntax highlighting
- **Django-TUI** - Inspect and run Django commands
- **Toad** - Beautiful terminal front-end for AI coding tools
- **Posting** - API development and testing tool

### Creative Applications

- **Pain** - MS Paint recreation in terminal
- **Upiano** - Piano instrument you can play
- **Usolitaire** - Solitaire with Unicode cards
- **Conway's Game of Life** - Cellular automata visualization

### Productivity Apps

- **Elia** - ChatGPT terminal client
- **Frogmouth** - Markdown browser
- **NoteSH** - Sticky notes app
- **Toolong** - Log file viewer with search and merge

### Data & System Tools

- **RecoverPy** - Recover deleted files interactively
- **Dunk** - Enhanced git diff visualization
- **SSHaMan** - SSH connection manager
- **HumBLE Explorer** - Bluetooth LE scanner

---

## 11. Plugins & Extensions

### textual-plotext

Terminal charts and graphs:

```python
from textual_plotext import PlotextPlot

class ChartApp(App):
    def compose(self) -> ComposeResult:
        yield PlotextPlot()

    def on_mount(self):
        plt = self.query_one(PlotextPlot).plt

        # Scatter plot
        y = plt.sin()
        plt.scatter(y)
        plt.title("Neural Network Activity")

        # Bar chart
        plt.bar([1, 2, 3], [10, 20, 15])

        # Time series
        plt.date_form("H:M:S")
        plt.plot(dates, values)
```

**Supported:** scatter, line, bar, histogram, candlestick, error plots, confusion matrices

### Other Useful Libraries

- **textual-autocomplete** - Dropdown with search
- **textual-imageview** - Terminal image viewer
- **textual-fspicker** - Filesystem navigation
- **palettepal** - Color editor and palette generator

---

## 12. Sci-Fi UI Specific Recommendations

### For MoE Debate System

**Animation Effects:**
- Pulse agent status indicators with opacity animation
- Slide transitions between debate rounds
- Fade in/out for agent responses
- Breathing effects on active agent labels

**Visual Style:**
- Cyan/magenta gradients for futuristic feel
- Figlet banners for section headers
- Unicode block characters for data visualization
- Sparklines for real-time score tracking

**Layout:**
- Grid layout for agent cards (3 columns)
- Modal screens for detailed agent views
- Layered overlays for system notifications
- Screen stack for navigation (overview → detail → analysis)

**Data Display:**
- DataTable with live score updates
- Progress bars for response generation
- Loading indicators during model inference
- Toast notifications for agent events

**Performance:**
- Expect 60 FPS animations on modern terminals
- Handle 100+ widgets without performance issues
- Use reactive attributes for automatic UI updates
- Leverage partial rendering for efficiency

### Code Example: Sci-Fi Agent Card

```python
from textual.app import App, ComposeResult
from textual.widgets import Static
from textual.reactive import reactive
from textual_pyfiglet import FigletWidget

class AgentCard(Static):
    score = reactive(0.0)
    status = reactive("IDLE")

    def compose(self) -> ComposeResult:
        yield FigletWidget(
            text="A-1",
            font="banner3",
            gradient_start_color="cyan",
            gradient_end_color="magenta",
            animate=True
        )
        yield Static(id="status")
        yield Static(id="score")

    def watch_score(self, new_score):
        score_widget = self.query_one("#score")
        score_widget.update(f"[bold cyan]SCORE: {new_score:.1f}[/]")

        # Pulse animation on score change
        score_widget.styles.animate("opacity", 0.3, duration=0.2)
        score_widget.styles.animate("opacity", 1.0, duration=0.3, delay=0.2)

    def watch_status(self, new_status):
        status_widget = self.query_one("#status")

        color = {
            "IDLE": "grey50",
            "ACTIVE": "green blink",
            "THINKING": "yellow",
            "COMPLETE": "cyan"
        }[new_status]

        status_widget.update(f"[{color}]● {new_status}[/]")
```

---

## Sources & References

1. [Textual Official Documentation](https://textual.textualize.io/)
2. [Textual Animation Guide](https://textual.textualize.io/guide/animation/)
3. [Textual Reactivity Guide](https://textual.textualize.io/guide/reactivity/)
4. [Textual Screens Guide](https://textual.textualize.io/guide/screens/)
5. [Textual CSS Guide](https://textual.textualize.io/guide/CSS/)
6. [Textual Renderables API](https://textual.textualize.io/api/renderables/)
7. [Rich Library GitHub](https://github.com/Textualize/rich)
8. [textual-canvas GitHub](https://github.com/davep/textual-canvas)
9. [textual-plotext](https://github.com/Textualize/textual-plotext)
10. [textual-pyfiglet](https://github.com/edward-jazzhands/textual-pyfiglet)
11. [Awesome Textual Projects](https://oleksis.github.io/awesome-textualize-projects/)
12. [High Performance Terminal Apps](https://textual.textualize.io/blog/2024/12/12/algorithms-for-high-performance-terminal-apps/)
13. [Textual DataTable Widget](https://textual.textualize.io/widgets/data_table/)
14. [Real Python - Textual Tutorial](https://realpython.com/python-textual/)
15. [Textual GitHub Repository](https://github.com/Textualize/textual)
