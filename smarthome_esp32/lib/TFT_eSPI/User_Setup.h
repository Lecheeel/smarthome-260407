// User_Setup.h for ST7735 1.8" 128x160 TFT display

#define ST7735_DRIVER

// ESP32 S3 pins for ST7735 display
#define TFT_WIDTH  128
#define TFT_HEIGHT 160

#define TFT_RST   6   // IO6 - Reset
#define TFT_RS    7   // IO7 - Data/Command (DC)
#define TFT_CS    10  // IO10 - Chip Select

#define TFT_SCLK  12  // IO12 - SPI Clock
#define TFT_MOSI  11  // IO11 - SPI Data (MOSI)

//#define TFT_MISO  -1  // Not used for display

#define TFT_BL    -1  // Backlight pin (-1 if not used)

#define TFT_BACKLIGHT_ON HIGH

// SPI settings
#define SPI_FREQUENCY  27000000  // 27MHz SPI clock

// Color order for ST7735
#define TFT_RGB_ORDER TFT_RGB  // RGB color order

// Invert display colors
#define TFT_INVERSION_ON

// Enable SPIFFS for loading images (optional)
//#define USE_SPIFFS

// Define the SPI bus to use (VSPI is default for ESP32)
#define TFT_SPI_HOST VSPI_HOST
