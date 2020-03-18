import train
import convnet_ai
import ai as ai_module

ai = convnet_ai.RotatedCenteredAI("models_output/centered-rotated-ai-2020-03-18 16:37:36-above-7.h5")

for _ in range(10):
    trainer = train.Trainer(ai, 512)
    trainer.simulate_entire_game()
    max_score, total_score = trainer.results()
    print("max_score:", max_score, "avg_score:", total_score / 512)
