import { NgClass, DecimalPipe } from "@angular/common";
import { Component, inject } from "@angular/core";
import { FormBuilder, ReactiveFormsModule, Validators } from "@angular/forms";
import { Router, RouterLink } from "@angular/router";
import { SceneService } from "../../core/services/scene.service";
import { finalize } from "rxjs";

@Component({
    selector: 'app-new-project',
    standalone: true,
    imports: [ReactiveFormsModule, RouterLink, NgClass, DecimalPipe],
    templateUrl: './new-project.component.html',
    styleUrl: './new-project.component.scss',
})
export class NewProjectComponent {
    private readonly formBuilder = inject(FormBuilder)
    private readonly sceneService = inject(SceneService)
    private readonly router = inject(Router)

    selectedFile: File | null = null;
    isSubmitting = false;
    errorMessage: string | null = null;

    readonly form = this.formBuilder.nonNullable.group({
        sceneName: [
            '',
            [
                Validators.required,
                Validators.minLength(3),
                Validators.pattern(/^[a-zA-Z0-9_-]+$/),
            ],
        ],
    });

    onFileSelected(event: Event): void {
        const input = event.target as HTMLInputElement;
        const file = input.files?.[0] ?? null;

        this.selectedFile = file;
        this.errorMessage = null
    }

    submitVideo(): void {
        this.errorMessage = null;

        if (this.form.invalid) {
            this.form.markAllAsTouched();
            return
        }

        if (!this.selectedFile) {
            this.errorMessage = "You must select a video file"
            return;
        }

        const sceneName = this.form.controls.sceneName.value;

        this.isSubmitting = true;

        this.sceneService
            .createScene(sceneName, this.selectedFile)
            .pipe(finalize(() => (this.isSubmitting = false)))
            .subscribe({
                next: (scene) => {
                    console.log("Scene created", scene);
                    this.router.navigate(['/dashboard']);
                },
                error: (error) => {
                    console.error('Error creating scene:', error);

                    this.errorMessage = error?.error?.detail ?? 
                    'Could not create the project. Check the backend logs.';
                },
            });
    }

    get sceneNameInvalid(): boolean {
        const controlSceneName = this.form.controls.sceneName;
        return controlSceneName.invalid && (controlSceneName.dirty || controlSceneName.touched)
    }
}